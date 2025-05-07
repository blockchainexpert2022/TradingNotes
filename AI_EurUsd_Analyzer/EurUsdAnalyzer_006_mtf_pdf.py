# first send all timeframes and the pdf if there is any (about trading, I use an ICT ebook)
# then loops with 1m screenshots until it finds an optimal trade entry

!pip install selenium pillow requests google-generativeai
!apt-get update
!apt-get install -y chromium-chromedriver

import requests
import time
import os
import io
from PIL import Image
import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import shutil
from selenium.common.exceptions import WebDriverException
import glob
import google.generativeai as genai

# Configuration
actifs = ["EURUSD"]
timeframes_init = ["1", "5", "15", "60", "240", "1D", "1W"]  # Pour analyse initiale
timeframe_monitor = "1"  # Pour monitoring en boucle
gemini_api_key = "REPLACE_ME"  # Remplacez par votre clé API
chemin_enregistrement = "/tmp/screenshots"
chemin_pdf = "/tmp/pdf"
os.makedirs(chemin_enregistrement, exist_ok=True)
os.makedirs(chemin_pdf, exist_ok=True)

# Configure Gemini
genai.configure(api_key=gemini_api_key)

def reset_environnement():
    """Nettoie les dossiers de travail"""
    for folder in [chemin_enregistrement]: #chemin_pdf
        if os.path.exists(folder):
            shutil.rmtree(folder)
            os.makedirs(folder)
    print("Environnement réinitialisé")

reset_environnement()

def prendre_screenshot_tradingview(actif, timeframe):
    """Capture un screenshot pour un actif et timeframe donné"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    try:
        from google.colab import drive
        options.binary_location = "/usr/bin/chromium-browser"
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Erreur initialisation navigateur: {e}")
        return None

    url = f"https://fr.tradingview.com/chart/?symbol={actif}&interval={timeframe}"
    driver.get(url)

    try:
        WebDriverWait(driver, 20).until(lambda d: d.find_element(By.TAG_NAME, "body"))
        time.sleep(5)  # Attendre le chargement complet
        
        nom_fichier = os.path.join(chemin_enregistrement, f"{actif}_{timeframe}.png")
        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe} sauvegardé")
        return nom_fichier
    except Exception as e:
        print(f"Erreur capture {actif} {timeframe}: {e}")
        return None
    finally:
        driver.quit()

def trouver_pdfs():
    """Retourne le premier PDF trouvé dans le dossier"""
    if os.path.exists(chemin_pdf):
        pdfs = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
        return pdfs[0] if pdfs else None
    return None

def initialiser_session_gemini():
    """Initialise une session Gemini avec contexte"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    chat = model.start_chat(history=[])
    return chat

def envoyer_analyse_initiale(chat, chemins_images, chemin_pdf=None):
    """Envoie l'analyse initiale avec tous les timeframes"""
    content = [
        "ANALYSE INITIALE - Vous êtes un expert en analyse technique ICT. ",
        "Analysez ces graphiques multi-timeframes et préparez-vous à recevoir des mises à jour du 1m.",
        "Timeframes fournis: " + ", ".join(timeframes_init),
        "Critères de confirmation ICT:",
        "1. Confluence multi-timeframe",
        "2. Structure de marché cohérente",
        "3. Niveaux de liquidité clairs",
        "4. Alignment temporel ICT",
        "5. Configuration d'entrée précise"
    ]
    
    # Ajouter les images
    for img_path in chemins_images:
        try:
            img = Image.open(img_path)
            content.append(f"Graphique {os.path.basename(img_path)}:")
            content.append(img)
        except Exception as e:
            print(f"Erreur chargement image {img_path}: {e}")
    
    # Ajouter le PDF si disponible
    if chemin_pdf:
        try:
            content.append("Document de référence:")
            content.append(genai.upload_file(chemin_pdf))
        except Exception as e:
            print(f"Erreur chargement PDF: {e}")
    
    # Demande d'analyse complète
    content.append("""
    Fournissez une analyse complète avec:
    1. Synthèse multi-timeframe
    2. Niveaux clés à surveiller
    3. Scénarios favorables
    4. Préparation pour le monitoring du 1m
    """)
    
    response = chat.send_message(content)
    print("=== ANALYSE INITIALE COMPLETE ===")
    print(response.text)
    print("=== DEBUT DU MONITORING 1m ===")
    return response.text

def analyser_screenshot_1m(chat, chemin_image):
    """Analyse un screenshot 1m dans le contexte existant"""
    try:
        img = Image.open(chemin_image)
        response = chat.send_message([
            "MISE A JOUR 1m - Analysez ce graphique selon le contexte initial. Répondez avec:",
            "1. 'CONFIRME' si toutes les conditions ICT sont remplies pour un trade",
            "2. Sinon, 'ATTENDRE' et les éléments manquants",
            "3. Les niveaux clés à surveiller",
            img
        ])
        return response.text
    except Exception as e:
        print(f"Erreur analyse screenshot: {e}")
        return None

# Execution principale
if __name__ == "__main__":
    # Initialisation
    pdf = trouver_pdfs()
    chat_session = initialiser_session_gemini()
    
    # Capture des screenshots initiaux
    print("Capture des timeframes initiaux...")
    chemins_images_init = []
    for actif in actifs:
        for timeframe in timeframes_init:
            screenshot = prendre_screenshot_tradingview(actif, timeframe)
            if screenshot:
                chemins_images_init.append(screenshot)
            time.sleep(3)  # Pause entre les captures
    
    # Envoi de l'analyse initiale
    envoyer_analyse_initiale(chat_session, chemins_images_init, pdf)
    
    # Nettoyage des screenshots initiaux
    for img in chemins_images_init:
        try:
            os.remove(img)
        except:
            pass
    
    # Boucle de monitoring du 1m
    confirmation = False
    compteur_analyses = 0
    max_analyses = 100  # Limite de sécurité
    
    while not confirmation and compteur_analyses < max_analyses:
        compteur_analyses += 1
        print(f"\nMonitoring 1m - Analyse n°{compteur_analyses} - {time.strftime('%H:%M:%S')}")
        
        # Capture et analyse du 1m
        screenshot = prendre_screenshot_tradingview(actif, timeframe_monitor)
        if screenshot:
            analyse = analyser_screenshot_1m(chat_session, screenshot)
            print(analyse)
            
            # Vérifier confirmation
            if analyse and "CONFIRME" in analyse:
                confirmation = True
                print("\n=== TRADE CONFIRMÉ ===")
                print("Tous les critères ICT sont validés sur le 1m dans le contexte multi-timeframe")
                print("=== FIN DE L'ANALYSE ===")
                break
            
            # Nettoyer le screenshot
            try:
                os.remove(screenshot)
            except:
                pass
            
            # Attendre avant prochaine analyse
            time.sleep(60)  # 1 minute entre les analyses
        
        else:
            print("Échec de capture, nouvelle tentative...")
            time.sleep(10)
    
    if not confirmation:
        print("Maximum d'analyses atteint sans confirmation")
    
    print("Processus terminé")
