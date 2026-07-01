"""
Real or AI? - a little game: you vs your model.

Run it from this folder:
    streamlit run guess_game.py

You see an image, guess "Real" or "AI", then the app reveals the truth
AND what your fine-tuned ResNet18 predicted. It keeps score for both of you.
"""
import os
import glob
import random

import numpy as np
import streamlit as st
import torch
import torch.nn as nn
from PIL import Image
from torchvision.models import resnet18, ResNet18_Weights
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

DATA_DIR = "data_real_vs_ai"
MODEL_PATH = "real_vs_ai_resnet18.pt"
CLASSES = ["ai", "real"]  # index order matches how the model was trained (ImageFolder sorts alphabetically)

st.set_page_config(page_title="Real or AI?", page_icon="🕵️")


@st.cache_resource
def load_model():
    weights = ResNet18_Weights.IMAGENET1K_V1
    model = resnet18()
    model.fc = nn.Linear(512, 2)
    model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    model.eval()
    return model, weights.transforms()


def gradcam_overlay(model, preprocess, pil, target_idx):
    "heatmap of where the model looked, for the given class, as an RGB image"
    rgb = np.array(pil.resize((224, 224))).astype(np.float32) / 255.0
    x = preprocess(pil).unsqueeze(0)
    with GradCAM(model=model, target_layers=[model.layer4[-1]]) as cam:
        heat = cam(input_tensor=x, targets=[ClassifierOutputTarget(target_idx)])[0]
    return show_cam_on_image(rgb, heat, use_rgb=True)


@st.cache_data
def load_pool():
    "list of (path, true_label_index) for every image in both folders"
    pool = []
    for idx, cls in enumerate(CLASSES):
        for p in glob.glob(os.path.join(DATA_DIR, cls, "*")):
            if p.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                pool.append((p, idx))
    return pool


def model_predict(model, preprocess, pil):
    with torch.no_grad():
        logits = model(preprocess(pil).unsqueeze(0))
        probs = torch.softmax(logits, dim=1)[0]
    pred = int(probs.argmax())
    return pred, float(probs[pred])


# ---- guards ----
if not os.path.exists(MODEL_PATH):
    st.error(f"Model file '{MODEL_PATH}' not found. Run the notebook first to train & save it.")
    st.stop()

model, preprocess = load_model()
pool = load_pool()
if not pool:
    st.error(f"No images found in '{DATA_DIR}/'. Expected '{DATA_DIR}/real/' and '{DATA_DIR}/ai/'.")
    st.stop()

# ---- game state ----
ss = st.session_state
if "order" not in ss:
    ss.order = random.sample(range(len(pool)), len(pool))
    ss.pos = 0
    ss.human_score = 0
    ss.model_score = 0
    ss.rounds = 0
    ss.revealed = False
    ss.human_guess = None
    ss.model_guess = None
    ss.model_conf = None


def next_index():
    if ss.pos >= len(ss.order):          # ran through the whole pool -> reshuffle
        ss.order = random.sample(range(len(pool)), len(pool))
        ss.pos = 0
    return ss.order[ss.pos]


def make_guess(label):
    "label: 'real' or 'ai'"
    path, true_idx = pool[next_index()]
    pil = Image.open(path).convert("RGB")
    m_pred, m_conf = model_predict(model, preprocess, pil)

    ss.human_guess = label
    ss.model_guess = CLASSES[m_pred]
    ss.model_conf = m_conf
    ss.true_label = CLASSES[true_idx]
    ss.current_path = path
    ss.revealed = True
    ss.rounds += 1
    if label == ss.true_label:
        ss.human_score += 1
    if ss.model_guess == ss.true_label:
        ss.model_score += 1


def next_round():
    ss.pos += 1
    ss.revealed = False


# ---- UI ----
st.title("🕵️ Real or AI?")
st.caption("Guess whether the image is a real photo or AI-generated. Then see if you beat your model.")

# scoreboard
c1, c2, c3 = st.columns(3)
c1.metric("Round", ss.rounds)
acc_h = f"{ss.human_score}/{ss.rounds}" if ss.rounds else "0/0"
acc_m = f"{ss.model_score}/{ss.rounds}" if ss.rounds else "0/0"
c2.metric("🧑 You", acc_h)
c3.metric("🤖 Model", acc_m)
st.divider()

# current image
if not ss.revealed:
    path, _ = pool[next_index()]
    ss.current_path = path

img = Image.open(ss.current_path).convert("RGB").resize((320, 320), Image.LANCZOS)
st.image(img, caption="What is this?", width=320)

if not ss.revealed:
    b1, b2 = st.columns(2)
    if b1.button("📷 Real", use_container_width=True):
        make_guess("real"); st.rerun()
    if b2.button("🤖 AI", use_container_width=True):
        make_guess("ai"); st.rerun()
else:
    you_ok = ss.human_guess == ss.true_label
    model_ok = ss.model_guess == ss.true_label
    st.markdown(f"### Truth: **{ss.true_label.upper()}**")
    st.write(f"🧑 You guessed **{ss.human_guess}** - {'✅ correct' if you_ok else '❌ wrong'}")
    st.write(f"🤖 Model guessed **{ss.model_guess}** - {'✅ correct' if model_ok else '❌ wrong'}")
    st.progress(ss.model_conf, text=f"model was {ss.model_conf:.0%} sure it's {ss.model_guess}")
    if you_ok and not model_ok:
        st.success("You beat the model this round! 🎉")
    elif model_ok and not you_ok:
        st.info("The model got this one and you didn't.")
    st.button("Next ▶", use_container_width=True, on_click=next_round)

    # overall standings
    if ss.human_score > ss.model_score:
        st.markdown(f"**Overall: 🧑 you lead {ss.human_score}-{ss.model_score}**")
    elif ss.model_score > ss.human_score:
        st.markdown(f"**Overall: 🤖 model leads {ss.model_score}-{ss.human_score}**")
    else:
        st.markdown(f"**Overall: tied {ss.human_score}-{ss.model_score}**")

    # explanation: where the model looked (opens automatically when you were wrong)
    with st.expander("🔍 Why? — where the model looked", expanded=not you_ok):
        pil = Image.open(ss.current_path).convert("RGB")
        overlay = gradcam_overlay(model, preprocess, pil, CLASSES.index(ss.model_guess))
        st.image(overlay, width=320,
                 caption=f"Grad-CAM: hot (red) = pixels that pushed the model toward '{ss.model_guess}'")
        st.caption(
            "This shows what drove the **model's** decision, not absolute proof. "
            "Common StyleGAN tells to eyeball yourself: asymmetric eyes/pupils, mismatched "
            "earrings, melting hair strands, warped or blurry background, odd teeth/glasses, edge artifacts."
        )

st.divider()
if st.button("Reset game"):
    for k in list(ss.keys()):
        del ss[k]
    st.rerun()
