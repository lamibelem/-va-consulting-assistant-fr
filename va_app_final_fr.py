import streamlit as st
import json
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from PyPDF2 import PdfReader
import fitz
import pytesseract
from PIL import Image
from fpdf import FPDF
import os
import csv
import io

# --- Configuration Azure ---
endpoint = "https://DeepSeek-R1-iidkm.eastus2.models.ai.azure.com"
api_key = "u2tl0lAkttAf0dEDO4UP7yxYfxpCKSQt"
model_name = "DeepSeek-R1-iidkm"

# --- Chargement des prompts ---
with open("prompt_cards.json", "r", encoding="utf-8") as f:
    prompt_data = json.load(f)

prompt_options = [card["title"] for card in prompt_data]
prompt_descriptions = {card["title"]: card["description"] for card in prompt_data}
prompts = {card["title"]: card["prompt"] for card in prompt_data}

st.set_page_config(page_title="Assistant Fiscal – VA Consulting", layout="centered")
# st.image("va_logo.jpg", width=200)
st.title("VA CONSULTING – Assistant Fiscal IA")
st.markdown("""
Bienvenue dans votre assistant fiscal intelligent, conçu pour répondre à toutes vos questions fiscales en Afrique de l’Ouest francophone. Posez une question ou téléversez un document pour obtenir des réponses précises, rapides et adaptées aux réglementations locales.
""")

mode_assistant = st.selectbox("🧠 Choisissez un mode d'assistance :", prompt_options, help=prompt_descriptions[prompt_options[0]])
st.caption(f"💡 {prompt_descriptions[mode_assistant]}")

# --- Informations utilisateur ---
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    nom_utilisateur = st.text_input("👤 Votre nom complet")
    entreprise_utilisateur = st.text_input("🏢 Nom de votre entreprise")
with col2:
    email_utilisateur = st.text_input("📧 Votre adresse email")
    paiement_effectue = st.checkbox("✅ J'ai payé 2 000 XOF via Orange Money")

st.markdown("""
💰 **Accès mensuel : 2 000 XOF**  
Effectuez votre paiement via **Orange Money** au : **+226 76 43 73 58**
---
""")

# --- Question directe ---
st.markdown("### 🧾 Posez une question fiscale")
question_utilisateur = st.text_input("Écrivez votre question ici")
if question_utilisateur:
    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    reponse = client.complete(
        messages=[
            SystemMessage(content=prompts[mode_assistant]),
            UserMessage(content=question_utilisateur),
        ],
        max_tokens=2048,
        model=model_name
    )
    resultat = reponse.choices[0].message.content
    st.success(resultat)

    # Export PDF avec support UTF-8
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=12)
    pdf.multi_cell(0, 10, txt=resultat)
    pdf_output = pdf.output(dest="S").encode("latin-1", "ignore")
    st.download_button("📄 Télécharger la réponse en PDF", data=pdf_output, file_name="reponse_va.pdf", mime="application/pdf")

    if email_utilisateur:
        try:
            with open("va_leads.csv", "a", newline="", encoding="utf-8") as file:
                csv.writer(file).writerow([nom_utilisateur, entreprise_utilisateur, email_utilisateur, question_utilisateur, resultat])
        except:
            st.warning("⚠️ Erreur lors de l'enregistrement des informations.")

# --- Téléversement de document ---
st.markdown("### 📂 Ou téléversez un document fiscal (.pdf ou .txt)")
fichier = st.file_uploader("Téléverser un fichier", type=["pdf", "txt"])
if fichier:
    donnees = fichier.getvalue()
    texte = ""

    if fichier.type == "application/pdf":
        try:
            pdf = PdfReader(io.BytesIO(donnees))
            texte = "\n".join([page.extract_text() or "" for page in pdf.pages])
        except:
            texte = ""

        if not texte.strip():
            st.info("📷 PDF scanné détecté. OCR en cours...")
            try:
                doc = fitz.open(stream=donnees, filetype="pdf")
                for page in doc:
                    img = Image.open(io.BytesIO(page.get_pixmap(dpi=300).tobytes()))
                    texte += pytesseract.image_to_string(img, lang="fra")
            except:
                st.error("❌ Échec de l'extraction de texte.")
                st.stop()
    else:
        texte = donnees.decode("utf-8")

    if not texte.strip():
        st.warning("⚠️ Aucun texte exploitable trouvé.")
    else:
        st.write("✏️ Résultat OCR (vous pouvez corriger ci-dessous) :")
        texte_corrige = st.text_area("Modifier le texte extrait :", value=texte[:10000], height=300)

        def decouper_texte(texte, max_len=3000, chevauchement=500):
            blocs, i = [], 0
            while i < len(texte):
                blocs.append(texte[i:i+max_len])
                i += max_len - chevauchement
            return blocs

        blocs_texte = decouper_texte(texte_corrige)

        client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
        if st.button("🧠 Résumer le document complet"):
            resumes = []
            for i, bloc in enumerate(blocs_texte):
                st.info(f"Traitement du bloc {i+1}/{len(blocs_texte)}...")
                rep = client.complete(
                    messages=[
                        SystemMessage(content=prompts[mode_assistant]),
                        UserMessage(content=bloc),
                    ],
                    max_tokens=2048,
                    model=model_name
                )
                resumes.append(rep.choices[0].message.content)

            resume_final = "\n".join(resumes)
            st.success(resume_final)

            suivi = st.text_input("🔄 Posez une question complémentaire basée sur ce résumé :")
            if suivi:
                reponse_suivi = client.complete(
                    messages=[
                        SystemMessage(content=prompts[mode_assistant]),
                        UserMessage(content=resume_final[:3000]),
                        AssistantMessage(content=resume_final),
                        UserMessage(content=suivi),
                    ],
                    max_tokens=2048,
                    model=model_name
                )
                st.success(reponse_suivi.choices[0].message.content)