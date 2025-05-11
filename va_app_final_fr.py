import streamlit as st
import json
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from PyPDF2 import PdfReader
import pytesseract
from pdf2image import convert_from_bytes
import os
import smtplib
from email.message import EmailMessage
import csv
import io
import langdetect
from fpdf import FPDF

# --- Configuration Azure ---
endpoint = "https://DeepSeek-R1-iidkm.eastus2.models.ai.azure.com"
api_key = "u2tl0lAkttAf0dEDO4UP7yxYfxpCKSQt"
model_name = "DeepSeek-R1-iidkm"

# --- Chargement des cartes de prompts ---
with open("prompt_cards.json", "r", encoding="utf-8") as f:
    prompt_data = json.load(f)

prompt_options = [card["title"] for card in prompt_data]
prompt_descriptions = {card["title"]: card["description"] for card in prompt_data}
prompts = {card["title"]: card["prompt"] for card in prompt_data}

# --- UI ---
st.set_page_config(page_title="VA CONSULTING – Assistant Fiscal AI", layout="centered")
st.image("va_logo.jpg", width=200)
st.title("VA CONSULTING – Assistant Fiscal AI")

st.markdown("""
Bienvenue dans votre assistant fiscal intelligent. Posez une question ou téléversez un document fiscal pour recevoir des réponses rapides et adaptées aux règles fiscales d’Afrique de l’Ouest.
""")

# --- Sélecteur de prompt ---
prompt_mode = st.selectbox("🧠 Choisissez un Mode d'Assistance:", prompt_options, help=prompt_descriptions[prompt_options[0]])
st.caption(f"💡 {prompt_descriptions[prompt_mode]}")

# --- Informations utilisateur et paiement ---
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    nom_utilisateur = st.text_input("👤 Nom complet")
    societe_utilisateur = st.text_input("🏢 Société")
with col2:
    email_utilisateur = st.text_input("📧 Email")
    paiement_valide = st.checkbox("✅ J’ai payé 2 000 XOF via Orange Money")

st.markdown("""
💰 **Accès mensuel : 2 000 XOF**
📱 Paiement via **Orange Money** : **+226 76 43 73 58**
""")

# --- Saisie de question ---
st.markdown("### 🧾 Posez votre question fiscale")
question_utilisateur = st.text_input("Entrez votre question")
if question_utilisateur:
    langue = langdetect.detect(question_utilisateur)
    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    reponse = client.complete(
        messages=[
            SystemMessage(content=prompts[prompt_mode]),
            UserMessage(content=question_utilisateur)
        ],
        max_tokens=2048,
        model=model_name
    )
    resultat = reponse.choices[0].message.content
    st.success(resultat)

    # Génération PDF compatible UTF-8
    pdf = FPDF()
    pdf.add_page()

    font_path = os.path.join("fonts", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path)
        pdf.set_font("DejaVu", size=12)
    else:
        pdf.set_font("helvetica", size=12)

    pdf.multi_cell(0, 10, resultat)
    pdf_output = pdf.output(dest="S").encode("latin-1", "ignore")

    st.download_button("📄 Télécharger la réponse en PDF", data=pdf_output, file_name="reponse_va.pdf", mime="application/pdf")

    if email_utilisateur:
        try:
            with open("va_leads.csv", mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([nom_utilisateur, societe_utilisateur, email_utilisateur, question_utilisateur, resultat])
        except Exception:
            st.warning("⚠️ Impossible d'enregistrer dans le fichier CSV.")

# --- Téléversement de document ---
st.markdown("### 📄 Ou téléversez un document (.pdf ou .txt)")

fichier = st.file_uploader("Téléverser un document", type=["pdf", "txt"])
if fichier:
    texte = ""
    if fichier.type == "application/pdf":
        try:
            pdf = PdfReader(fichier)
            texte = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        except:
            texte = ""
        if not texte:
            st.info("🔎 Extraction OCR en cours...")
            images = convert_from_bytes(fichier.read())
            texte = "\n".join([pytesseract.image_to_string(img) for img in images])
    else:
        texte = fichier.read().decode("utf-8")

    if not texte.strip():
        st.warning("⚠️ Aucun texte lisible trouvé.")
    else:
        st.write("📑 Texte extrait :")
        st.code(texte[:1000])
        if st.button("📊 Résumer ce document"):
            client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
            reponse_doc = client.complete(
                messages=[
                    SystemMessage(content=prompts[prompt_mode]),
                    UserMessage(content=texte[:3000])
                ],
                max_tokens=2048,
                model=model_name
            )
            resume = reponse_doc.choices[0].message.content
            st.success(resume)

            suivi = st.text_input("💬 Question complémentaire sur ce document :")
            if suivi:
                reponse_suivi = client.complete(
                    messages=[
                        SystemMessage(content=prompts[prompt_mode]),
                        UserMessage(content=texte[:2000]),
                        AssistantMessage(content=resume),
                        UserMessage(content=suivi)
                    ],
                    max_tokens=2048,
                    model=model_name
                )
                st.success(reponse_suivi.choices[0].message.content)
