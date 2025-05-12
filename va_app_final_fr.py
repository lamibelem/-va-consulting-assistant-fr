import streamlit as st
import os
import io
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from fpdf import FPDF
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from langdetect import detect

# Azure configuration
endpoint = "https://DeepSeek-R1-iidkm.eastus2.models.ai.azure.com"
api_key = os.getenv("AZURE_API_KEY", "u2tl0lAkttAf0dEDO4UP7yxYfxpCKSQt")
model_name = "DeepSeek-R1-iidkm"

client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(api_key),
)

st.set_page_config(page_title="VA CONSULTING – Assistant Fiscal IA", layout="wide")
st.title("🤖 VA CONSULTING – Assistant Fiscal IA")

st.markdown("""
Bienvenue sur votre assistant fiscal alimenté par l'IA. Posez une question fiscale ou téléversez un document pour obtenir une réponse adaptée au contexte fiscal de l'UEMOA.

💬 *Exemples de questions :* "Quels sont les taux de TVA en vigueur ?", "Comment déclarer une société au Burkina Faso ?"
""")

nom_utilisateur = st.text_input("👤 Votre nom complet")
societe_utilisateur = st.text_input("🏢 Nom de votre société")
email_utilisateur = st.text_input("📧 Votre adresse e-mail")

# Prompt selector
prompt_options = {
    "💼 Conseils fiscaux UEMOA": "Vous êtes un assistant fiscal expert en fiscalité UEMOA. Répondez avec des références précises, en français clair, structuré et concis.",
    "📊 Analyse d’un document fiscal": "Vous êtes un auditeur fiscal. Analysez ce document selon les règles de la fiscalité UEMOA.",
    "🧾 Revue TVA et obligations déclaratives": "Vous êtes un expert en TVA en Afrique de l’Ouest. Donnez des conseils pratiques sur les obligations fiscales."
}

selected_prompt = st.selectbox("🧠 Choisissez un mode d’assistance :", list(prompt_options.keys()))

uploaded_file = st.file_uploader("📎 Téléverser un document PDF (facultatif)", type=["pdf"])
question_utilisateur = st.chat_input("💬 Posez votre question fiscale ici :")

if question_utilisateur:
    with st.spinner("Analyse en cours..."):
        contenu_extrait = ""

        if uploaded_file:
            try:
                reader = PdfReader(uploaded_file)
                for page in reader.pages:
                    contenu_extrait += page.extract_text() or ""
                if not contenu_extrait.strip():
                    images = convert_from_bytes(uploaded_file.read())
                    for image in images:
                        contenu_extrait += pytesseract.image_to_string(image)
            except Exception as e:
                st.error(f"Erreur lors de l'extraction du PDF : {e}")

        langue_detectee = detect(question_utilisateur)
        system_message = prompt_options[selected_prompt]

        if "historique" not in st.session_state:
            st.session_state.historique = []

        st.session_state.historique.append(UserMessage(content=question_utilisateur))

        messages = [
            SystemMessage(content=system_message)
        ] + st.session_state.historique

        response = client.complete(
            messages=messages,
            max_tokens=2048,
            model=model_name
        )

        resultat = response.choices[0].message.content

        # Hide or replace the "<think>...</think>" part if present
        if "<think>" in resultat and "</think>" in resultat:
            resultat = "**⏳ Traitement en cours...**\n\n" + resultat.split("</think>")[-1].strip()

        st.session_state.historique.append(AssistantMessage(content=resultat))

        st.markdown("## 🧠 Réponse IA :")
        for message in st.session_state.historique:
            if isinstance(message, UserMessage):
                with st.chat_message("👤 Utilisateur"):
                    st.markdown(message.content)
            elif isinstance(message, AssistantMessage):
                with st.chat_message("🤖 Assistant"):
                    st.markdown(message.content)

        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.add_font("NotoSans", "", "fonts/NotoSans-Regular.ttf", uni=True)
            pdf.set_font("NotoSans", size=12)
            pdf.multi_cell(0, 10, resultat)
            pdf_bytes = bytes(pdf.output(dest="S"))
            st.download_button("📄 Télécharger la réponse en PDF", data=pdf_bytes, file_name="reponse_va.pdf", mime="application/pdf")
        except Exception as e:
            st.warning(f"PDF download unavailable: {e}")

        if email_utilisateur:
            st.info(f"Une copie peut être envoyée à {email_utilisateur} prochainement (fonctionnalité en cours de développement).")
