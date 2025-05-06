# You can add PDFs files (about ICT trading for example) and ask Gemini to use the information in the PDF(s) to analyze the asset(s)

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
timeframes = ["1", "5", "15", "60", "240", "1D", "1W"]  # m1, m5, m15, h1, h4, daily, weekly
gemini_api_key = "REPLACE ME"  # Replace with your actual Gemini API key
chemin_enregistrement = "/tmp/screenshots"  # Dossier pour les captures
chemin_pdf = "/tmp/pdf"  # Dossier pour les PDFs à analyser
os.makedirs(chemin_enregistrement, exist_ok=True)
os.makedirs(chemin_pdf, exist_ok=True)  # Crée le dossier PDF s'il n'existe pas

# Configure the Gemini API
genai.configure(api_key=gemini_api_key)

def reset_environnement():
    """Nettoie les dossiers de travail"""
    for folder in [chemin_enregistrement]:
        if os.path.exists(folder):
            fichiers = glob.glob(os.path.join(folder, "*"))
            for fichier in fichiers:
                try:
                    if os.path.isfile(fichier):
                        os.remove(fichier)
                    elif os.path.isdir(fichier):
                        shutil.rmtree(fichier)
                except Exception as e:
                    print(f"Erreur suppression {fichier}: {e}")
            print(f"Dossier {folder} nettoyé")

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
        !apt-get update
        !apt install chromium-chromedriver
        options.binary_location = "/usr/bin/chromium-browser"
        driver = webdriver.Chrome(options=options)
    except ImportError:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Erreur initialisation navigateur: {e}")
        return None

    url = f"https://fr.tradingview.com/chart/?symbol={actif}&interval={timeframe}"
    driver.get(url)

    try:
        WebDriverWait(driver, 20).until(lambda d: d.find_element(By.TAG_NAME, "body"))
        time.sleep(5)
        
        actif_folder = os.path.join(chemin_enregistrement, actif)
        os.makedirs(actif_folder, exist_ok=True)
        
        nom_fichier = os.path.join(actif_folder, f"{actif}_{timeframe}.png")
        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe} sauvegardé")
        return nom_fichier
    except Exception as e:
        print(f"Erreur capture {actif} {timeframe}: {e}")
        return None
    finally:
        driver.quit()

def trouver_pdfs():
    """Retourne la liste des fichiers PDF dans le dossier dédié"""
    if os.path.exists(chemin_pdf):
        pdfs = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
        return pdfs
    return []

def envoyer_contenu_a_gemini(chemins_images, timeframes, chemins_pdfs=[]):
    """Envoie tous les contenus à Gemini pour analyse globale"""
    if not chemins_images and not chemins_pdfs:
        print("Aucun contenu à analyser")
        return None

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Préparation du prompt
        prompt = """analyser l'actif en fonction de ce qui est écrit dans le pdf"""
        
        #if chemins_pdfs:
        #    prompt += "\n\n4. Analyse relativement au contenu des PDF joints"
        
        # Préparation du contenu
        content = [prompt]
        
        # Ajout des images
        for img_path in chemins_images:
            content.append(Image.open(img_path))
        
        # Ajout des PDFs
        for pdf_path in chemins_pdfs:
            content.append(genai.upload_file(pdf_path))
        
        # Envoi à Gemini
        response = model.generate_content(content)
        return response.text
        
    except Exception as e:
        print(f"Erreur lors de l'envoi à Gemini: {e}")
        return None

# Execution principale
if __name__ == "__main__":
    for actif in actifs:
        # Capture des screenshots
        chemins_images = []
        timeframes_captures = []
        
        for timeframe in timeframes:
            screenshot = prendre_screenshot_tradingview(actif, timeframe)
            if screenshot:
                chemins_images.append(screenshot)
                timeframes_captures.append(timeframe)
            time.sleep(3)
        
        # Récupération des PDFs
        pdfs = trouver_pdfs()
        print(f"PDFs trouvés: {pdfs}")
        
        # Analyse globale
        if chemins_images or pdfs:
            analyse = envoyer_contenu_a_gemini(
                chemins_images, 
                timeframes_captures,
                pdfs
            )
            
            if analyse:
                print(f"\n=== ANALYSE COMPLETE POUR {actif} ===")
                print(analyse)
                print("="*50)
        
        # Nettoyage
        for img in chemins_images:
            try:
                os.remove(img)
            except:
                pass
    
    print("Traitement terminé")
