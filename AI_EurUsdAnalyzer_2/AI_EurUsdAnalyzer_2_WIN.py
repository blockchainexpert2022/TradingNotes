# Cette version de AI_EurUsdAnalyzer uploade des fichiers pdfs dans le contexte gemini distant
# et ne fait des analyses que sur les screenshots qui sont placés au fur et à mesure dans le répertoire manual_screenshots
# 1. Assurez-vous d'avoir installé les packages via pip :
# pip install pillow requests google-generativeai tenacity

import requests
import time
import os
import io
from PIL import Image
import shutil
import glob
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import re

# --- CRUCIAL: Clear potential proxy settings ---
proxy_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
for var_name in proxy_vars_to_clear:
    if var_name in os.environ:
        print(f"Clearing environment variable: {var_name}")
        del os.environ[var_name]
os.environ['NO_PROXY'] = '*'
# --- END CRUCIAL SECTION ---

# --- API KEY MANAGEMENT ---
gemini_api_key = "AIzaSyBifMdAQ2kT5IgunZZVU-52k-sJK9wYCuA" # REMPLACEZ PAR VOTRE VRAIE CLÉ

if not gemini_api_key or "VOTRE_CLE_API_GEMINI_ICI" in gemini_api_key or "AIzaSyB" not in gemini_api_key:
    raise ValueError("GEMINI_API_KEY n'est pas définie ou est toujours la valeur par défaut. Veuillez définir votre clé API réelle.")
# --- END API KEY MANAGEMENT ---

chemin_base = os.getcwd()
chemin_pdf = os.path.join(chemin_base, "pdf_files")
chemin_manual_screenshots = os.path.join(chemin_base, "manual_screenshots")
chemin_processed_screenshots = os.path.join(chemin_base, "processed_screenshots")

os.makedirs(chemin_pdf, exist_ok=True)
os.makedirs(chemin_manual_screenshots, exist_ok=True)
os.makedirs(chemin_processed_screenshots, exist_ok=True)

try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise

def trouver_tous_pdfs():
    if not os.path.exists(chemin_pdf):
        print(f"PDF directory not found: {chemin_pdf}")
        return []
    pdfs_paths = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
    if not pdfs_paths:
        print(f"No PDF found in {chemin_pdf}")
    return pdfs_paths

def initialiser_session_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # ou 'gemini-1.5-pro-latest' pour potentiellement de meilleurs résultats
    initial_prompt = """Vous êtes un expert en analyse technique ICT (Inner Circle Trader).
    Votre mission est d'analyser les documents PDF de référence (qui pourront être fournis initialement et/ou ajoutés en cours de session)
    et les captures d'écran de graphiques financiers que je vais vous envoyer.
    Pour chaque capture d'écran, fournissez une analyse ICT détaillée en tenant compte de TOUS les PDF de référence
    fournis jusqu'à présent et de l'historique de notre conversation.
    Identifiez la structure du marché, les POI (FVG, OB), la liquidité, et les scénarios potentiels.
    Si vous identifiez une opportunité de trade claire, proposez un plan de trade avec Entrée, Stop Loss, et Take Profit, avec justifications.
    Restez dans le contexte de notre conversation continue."""
    chat = model.start_chat(history=[
        {'role': 'user', 'parts': [initial_prompt]},
        {'role': 'model', 'parts': ["Compris. Je suis prêt à analyser les PDF (initiaux et ceux ajoutés ultérieurement) et les captures d'écran. J'utiliserai les concepts ICT et maintiendrai le contexte de notre conversation."]}
    ])
    return chat

RETRYABLE_GEMINI_EXCEPTIONS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, TimeoutError)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
    reraise=True
)
def send_message_to_gemini_with_retry(chat_session, content_parts, operation_description="Gemini API call"):
    print(f"Attempting to send message for: {operation_description}")
    response = chat_session.send_message(content_parts, request_options={'timeout': 300.0})
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_liste_pdfs_a_gemini(chat, liste_chemins_pdf, message_introductif):
    if not liste_chemins_pdf:
        return True
    content_parts = [message_introductif]
    fichiers_pdf_uploads = []
    for pdf_path in liste_chemins_pdf:
        try:
            print(f"Uploading PDF: {os.path.basename(pdf_path)}")
            uploaded_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
            content_parts.append(f"\nDocument PDF '{os.path.basename(pdf_path)}':")
            content_parts.append(uploaded_file)
            fichiers_pdf_uploads.append(uploaded_file)
            print(f"PDF {os.path.basename(pdf_path)} uploaded successfully.")
            time.sleep(1)
        except Exception as e:
            print(f"Erreur lors de l'upload du PDF {os.path.basename(pdf_path)}: {e}")
    if not fichiers_pdf_uploads and liste_chemins_pdf:
        print("AVERTISSEMENT: Aucun des PDF spécifiés n'a pu être uploadé dans cette tentative.")
        return False
    if fichiers_pdf_uploads:
        try:
            response = send_message_to_gemini_with_retry(chat, content_parts, "Upload de documents PDF")
            print("=== RÉPONSE DE GEMINI À L'UPLOAD DES PDF ===")
            print(response.text)
            print("==========================================")
            return True
        except Exception as e:
            print(f"Erreur lors de l'envoi du message avec les PDF à Gemini: {e}")
            return False
    return True

def analyser_screenshots_manuels(chat, liste_chemins_screenshots):
    if not liste_chemins_screenshots:
        return

    content_parts_base = [ # Base du prompt, les images seront ajoutées après
        "Voici une ou plusieurs nouvelles captures d'écran de graphiques financiers pour analyse.",
        "Veuillez fournir une analyse ICT détaillée pour chaque image, en tenant compte de TOUS les PDF de référence fournis jusqu'à présent et de l'historique de notre conversation.",
        "\nPour chaque graphique fourni, veuillez IMPÉRATIVEMENT :",
        "1. **Identifier et indiquer clairement l'ACTIF et le TIMEFRAME visibles sur le graphique.** (Exemples de timeframes : M1, M5, M15, M30, H1, H4, D1, W1, MN). Si le nom du fichier fournit une indication, utilisez-la comme piste mais confirmez visuellement.",
        "2. Analyser la structure du marché actuelle (BOS, MSS, tendance).",
        "3. Identifier les Points d'Intérêt (POI) clés (FVG, Order Blocks, Breaker Blocks, Mitigation Blocks) avec leurs niveaux approximatifs.",
        "4. Identifier les zones de liquidité importantes (Buy-side BSL, Sell-side SSL, Inducement IDM).",
        "5. Déterminer si le prix est en zone Premium ou Discount par rapport au range pertinent.",
        "6. Noter toute SMT Divergence avec un actif corrélé pertinent (comme le DXY si l'actif semble être une paire de devises majeure et si des informations de corrélation ont été fournies ou peuvent être inférées).",
        "7. Décrire les scénarios de trading ICT probables (haussier et baissier) basés sur votre analyse.",
        "8. Si une opportunité de trade claire avec de fortes confluences ICT se présente MAINTENANT sur la base du graphique analysé :",
        "   `TRADE SUGGÉRÉ: [LONG/SHORT] sur [ACTIF IDENTIFIÉ]`",
        "   `TIMEFRAME DE CONFIRMATION : [TIMEFRAME IDENTIFIÉ SUR LE GRAPHIQUE]`",
        "   `NIVEAU D'ENTRÉE : [prix]`",
        "   `NIVEAU DE STOP LOSS (SL) : [prix]` (Justification ICT: ex: sous le dernier swing low après MSS)",
        "   `NIVEAU DE TAKE PROFIT (TP) : [prix]` (Justification ICT: ex: liquidité opposée, POI majeur)",
        "   `RAISONNEMENT ICT COMPLET : [Expliquez la confluence des signaux, la confirmation du timeframe, etc.]`",
        "\nSi plusieurs images sont fournies, analysez-les séquentiellement. Précisez pour chaque image l'actif et le timeframe que vous avez identifiés."
    ]
    
    # Pour l'envoi à Gemini, nous allons construire une nouvelle liste 'content_parts' à chaque fois
    # ou passer les images en tant que données binaires si cela aide à libérer les fichiers.
    # Pour l'instant, gardons l'envoi d'objets PIL Image car c'est supporté.

    images_a_envoyer_gemini = [] # Liste pour stocker les objets PIL.Image à envoyer

    for screenshot_path in liste_chemins_screenshots:
        try:
            print(f"Preparing screenshot for analysis: {os.path.basename(screenshot_path)}")
            # Utilisation du gestionnaire de contexte
            with Image.open(screenshot_path) as img:
                # L'API Gemini a besoin de l'objet PIL Image.
                # Une façon de s'assurer qu'on ne garde pas de verrou est de charger les données
                # de l'image en mémoire et de passer cela, plutôt que l'objet qui maintient le fichier ouvert.
                # Cependant, l'API `google-generativeai` est conçue pour prendre des objets PIL.Image.
                # On va la stocker temporairement pour l'envoyer, `img.close()` sera appelé à la sortie du `with`.
                # MAIS, si Gemini garde une référence interne, cela ne suffit pas.
                # Essayons de forcer le chargement des données de l'image pour la "détacher" du fichier.
                img.load() # Force le chargement des données de l'image depuis le fichier
                images_a_envoyer_gemini.append({
                    "path": screenshot_path, # Pour le nom du fichier dans le prompt
                    "pil_image": img.copy() # Envoyer une COPIE de l'image
                })
            # À ce stade, en sortant du bloc `with`, img (l'original) devrait être fermé.
            print(f"Image {os.path.basename(screenshot_path)} processed (context manager exited).")

        except FileNotFoundError:
            print(f"ERROR: Screenshot file not found: {screenshot_path}")
        except Exception as e:
            print(f"Erreur lors du chargement du screenshot {os.path.basename(screenshot_path)}: {e}")

    if not images_a_envoyer_gemini:
        print("Aucun screenshot valide à analyser.")
        return

    # Construire le prompt final avec les images
    final_content_parts = list(content_parts_base) # Commencer avec la base du prompt
    for item in images_a_envoyer_gemini:
        final_content_parts.append(f"\n--- Analyse de la capture d'écran suivante (Nom original: {os.path.basename(item['path'])}) ---")
        final_content_parts.append(item['pil_image'])

    try:
        response = send_message_to_gemini_with_retry(chat, final_content_parts, f"Analyse de {len(images_a_envoyer_gemini)} screenshot(s) manuels")
        print(f"=== ANALYSE DE GEMINI POUR {len(images_a_envoyer_gemini)} SCREENSHOT(S) ===")
        print(response.text)
        print("===================================================")

    except Exception as e:
        print(f"Erreur lors de l'envoi des screenshots à Gemini: {e}")
    # Le finally n'est plus nécessaire pour fermer les images ici si le `with` fonctionne correctement
    # et si `img.copy()` a bien détaché l'image du fichier.

    # Essayer de déplacer les fichiers APRÈS que la réponse de Gemini soit revenue
    # et que, espérons-le, toutes les références aux objets image soient libérées.
    print("Attempting to move processed screenshots...")
    time.sleep(1) # AJOUTÉ: Petite pause pour laisser le système libérer les fichiers

    for item in images_a_envoyer_gemini: # Utiliser la liste des images traitées
        screenshot_path = item['path']
        if os.path.exists(screenshot_path):
            try:
                destination_path = os.path.join(chemin_processed_screenshots, os.path.basename(screenshot_path))
                if os.path.exists(destination_path):
                    base, ext = os.path.splitext(os.path.basename(screenshot_path))
                    destination_path = os.path.join(chemin_processed_screenshots, f"{base}_{time.strftime('%Y%m%d%H%M%S')}_{int(time.time()*1000)%1000}{ext}")
                shutil.move(screenshot_path, destination_path)
                print(f"Screenshot {os.path.basename(screenshot_path)} moved to processed folder as {os.path.basename(destination_path)}.")
            except Exception as e_move:
                print(f"Could not move screenshot {os.path.basename(screenshot_path)}: {e_move}")
                # Si le déplacement échoue toujours, envisager une stratégie de renommage ou de copie+suppression
                # ou simplement logger l'erreur et continuer.



# --- Main Execution Block ---
if __name__ == "__main__":
    print("Initialisation du script d'analyse de screenshots manuels.")
    
    print("Initialisation de la session Gemini...")
    try:
        chat_session = initialiser_session_gemini()
    except Exception as e:
        print(f"Échec de l'initialisation de la session Gemini: {e}. Arrêt.")
        exit()

    pdfs_uploades = set()

    print("\nRecherche des PDF initiaux...")
    pdfs_actuels_dans_dossier = trouver_tous_pdfs()
    if pdfs_actuels_dans_dossier:
        message_intro_pdf = "Voici les documents PDF de référence initiaux pour notre analyse. Veuillez les prendre en compte pour toutes les analyses futures de captures d'écran :"
        if envoyer_liste_pdfs_a_gemini(chat_session, pdfs_actuels_dans_dossier, message_intro_pdf):
            for pdf_path in pdfs_actuels_dans_dossier:
                pdfs_uploades.add(pdf_path)
        else:
            print("Avertissement: Certains PDF initiaux n'ont pas pu être envoyés. Le contexte peut être incomplet.")
    else:
        print("Aucun PDF de référence initial trouvé.")

    print(f"\n--- Démarrage de la surveillance des dossiers ---")
    print(f"PDFs: {chemin_pdf}")
    print(f"Screenshots à analyser: {chemin_manual_screenshots}")
    print("Ctrl+C pour arrêter.")

    try:
        while True:
            tous_les_pdfs_maintenant = trouver_tous_pdfs()
            nouveaux_pdfs_a_uploader = []
            for pdf_path in tous_les_pdfs_maintenant:
                if pdf_path not in pdfs_uploades:
                    nouveaux_pdfs_a_uploader.append(pdf_path)
            
            if nouveaux_pdfs_a_uploader:
                print(f"\n{len(nouveaux_pdfs_a_uploader)} nouveau(x) PDF(s) détecté(s) :")
                for p in nouveaux_pdfs_a_uploader: print(f"  - {os.path.basename(p)}")
                
                message_update_pdf = "De nouveaux documents PDF de référence ont été ajoutés. Veuillez les prendre en compte pour les analyses futures, en complément des précédents :"
                if envoyer_liste_pdfs_a_gemini(chat_session, nouveaux_pdfs_a_uploader, message_update_pdf):
                    for pdf_path in nouveaux_pdfs_a_uploader:
                        pdfs_uploades.add(pdf_path)
                else:
                    print("Avertissement: Certains des nouveaux PDF n'ont pas pu être envoyés.")

            nouveaux_screenshots_a_analyser = []
            extensions_images = ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG")
            for ext in extensions_images:
                fichiers_images_trouves = glob.glob(os.path.join(chemin_manual_screenshots, ext))
                for fichier_image in fichiers_images_trouves:
                    nouveaux_screenshots_a_analyser.append(fichier_image)
            
            if nouveaux_screenshots_a_analyser:
                print(f"\n{len(nouveaux_screenshots_a_analyser)} screenshot(s) à analyser détecté(s) dans '{os.path.basename(chemin_manual_screenshots)}':")
                
                analyser_screenshots_manuels(chat_session, nouveaux_screenshots_a_analyser)
                
                print(f"\nAttente de nouveaux fichiers...")

            if not nouveaux_pdfs_a_uploader and not nouveaux_screenshots_a_analyser:
                # print(".", end="", flush=True) # Optionnel, pour feedback visuel pendant l'attente
                pass

            time.sleep(10)

    except KeyboardInterrupt:
        print("\nArrêt du script par l'utilisateur.")
    except Exception as e_main:
        print(f"\nUne erreur inattendue est survenue dans la boucle principale : {e_main}")
    finally:
        print("Fin du script.")
