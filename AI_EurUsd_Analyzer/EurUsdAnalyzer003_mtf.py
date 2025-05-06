# This version takes one screenshot in one timeframe + sends it to gemini then takes the next one in another timeframe and so on...

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
chemin_enregistrement = "/tmp/screenshots"  # Use /tmp/ for Colab
os.makedirs(chemin_enregistrement, exist_ok=True)

# Configure the Gemini API
genai.configure(api_key=gemini_api_key)

def reset_environnement():
    """
    Efface tous les fichiers et répertoires dans le dossier de destination des captures d'écran.
    """
    if os.path.exists(chemin_enregistrement):
        fichiers = glob.glob(os.path.join(chemin_enregistrement, "*"))
        for fichier in fichiers:
            try:
                if os.path.isfile(fichier):
                    os.remove(fichier)
                    print(f"Fichier supprimé : {fichier}")
                elif os.path.isdir(fichier):
                    shutil.rmtree(fichier)
                    print(f"Répertoire supprimé : {fichier}")
            except Exception as e:
                print(f"Erreur lors de la suppression de {fichier} : {e}")
        try:
            shutil.rmtree(chemin_enregistrement)
            print(f"Répertoire {chemin_enregistrement} supprimé.")
        except Exception as e:
            print(f"Erreur lors de la suppression du répertoire {chemin_enregistrement} : {e}")

        os.makedirs(chemin_enregistrement, exist_ok=True)

# Efface l'environnement au démarrage du script
reset_environnement()

def prendre_screenshot_tradingview(actif, timeframe):
    """
    Prend une capture d'écran de la fenêtre du navigateur pour un actif sur TradingView avec un timeframe spécifique.

    Args:
        actif (str): Le symbole de l'actif (ex: "EURUSD")
        timeframe (str): Le timeframe (ex: "1" pour 1 minute, "1D" pour daily)

    Returns:
        str: Le chemin du fichier de la capture d'écran, ou None en cas d'erreur.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")  # Colab specific
    options.add_argument("--disable-dev-shm-usage")  # Colab specific
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--blink-settings=imagesEnabled=false")
    
    try:
        from google.colab import drive
        !apt-get update
        !apt install chromium-chromedriver
        options.binary_location = "/usr/bin/chromium-browser"
        driver = webdriver.Chrome(options=options)
    except ImportError:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print(f"WebDriverException lors de l'initialisation du navigateur : {e}")
        return None
    except Exception as e:
        print(f"Erreur lors de l'initialisation du navigateur : {e}")
        return None

    url_tradingview = f"https://fr.tradingview.com/chart/?symbol={actif}&interval={timeframe}"
    driver.get(url_tradingview)

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.find_element(By.TAG_NAME, "body")
        )
        time.sleep(5)  # Augmenté le temps d'attente pour le chargement des différents timeframes
        
        # Créer un sous-dossier pour l'actif s'il n'existe pas
        actif_folder = os.path.join(chemin_enregistrement, actif)
        os.makedirs(actif_folder, exist_ok=True)
        
        # Nom du fichier avec le timeframe
        nom_fichier = os.path.join(actif_folder, f"{actif}_{timeframe}.png")
        driver.save_screenshot(nom_fichier)
        print(f"Capture d'écran de {actif} (TF: {timeframe}) enregistrée : {nom_fichier}")
        return nom_fichier
    except WebDriverException as e:
        print(f"Erreur WebDriver lors de la capture d'écran de {actif} (TF: {timeframe}) : {e}")
        return None
    except Exception as e:
        print(f"Erreur lors de la capture d'écran de {actif} (TF: {timeframe}) : {e}")
        return None
    finally:
        driver.quit()

def envoyer_image_a_gemini(chemin_image, timeframe):
    """
    Envoie une image à l'API Gemini pour analyse avec mention du timeframe.

    Args:
        chemin_image (str): Le chemin du fichier image à envoyer.
        timeframe (str): Le timeframe de l'image

    Returns:
        str: La réponse textuelle de Gemini, ou None en cas d'erreur.
    """
    if not chemin_image:
        print("Aucun chemin d'image valide fourni.")
        return None

    try:
        # Load the image file
        img = Image.open(chemin_image)
        
        # Initialize the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Prepare the prompt with timeframe information
        prompt = f"Analyse ce graphique (timeframe: {timeframe}) selon les concepts avancés du trading ICT. Donne une analyse simple avec:\n"
        prompt += "- Validité pour une entrée long ou short\n"
        prompt += "- Si valide, propose un SL et un TP\n"
        prompt += "- Analyse des facteurs clés (liquidity, order blocks, etc.)\n"
        prompt += "- Niveau de confiance (1-5)"
        
        # Generate the response
        response = model.generate_content([prompt, img])
        
        return response.text
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'image à l'API Gemini : {e}")
        return None

# Boucle principale pour capturer et analyser les actifs sur tous les timeframes
if __name__ == "__main__":
    for actif in actifs:
        for timeframe in timeframes:
            chemin_screenshot = prendre_screenshot_tradingview(actif, timeframe)
            if chemin_screenshot:
                reponse_gemini = envoyer_image_a_gemini(chemin_screenshot, timeframe)
                if reponse_gemini:
                    print(f"\nAnalyse de Gemini pour {actif} (TF: {timeframe}):")
                    print(reponse_gemini)
                    print("-" * 50)
                else:
                    print(f"Aucune analyse disponible pour {actif} (TF: {timeframe})")
                # Optionnel: supprimer l'image après analyse pour économiser de l'espace
                # os.remove(chemin_screenshot)
            time.sleep(10)  # Pause entre les captures pour éviter de surcharger
    print("Script terminé.")
