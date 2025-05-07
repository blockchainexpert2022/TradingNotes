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
import google.generativeai as genai  # Correct import for Gemini

# Configuration
actifs = ["AAPL", "GOOGL", "EURUSD"]
gemini_api_key = "REPLACE_ME"  # Replace with your actual Gemini API key
chemin_enregistrement = "/tmp/screenshots"  # Use /tmp/ for Colab
os.makedirs(chemin_enregistrement, exist_ok=True)

# Configure the Gemini API
genai.configure(api_key=gemini_api_key)  # Correct configuration method

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

# Fonction pour prendre une capture d'écran d'un actif sur TradingView
def prendre_screenshot_tradingview(actif):
    """
    Prend une capture d'écran de la fenêtre du navigateur pour un actif sur TradingView.

    Args:
        actif (str): Le symbole de l'actif (ex: "AAPL", "GOOGL").

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

    url_tradingview = f"https://fr.tradingview.com/chart/?symbol={actif}"
    driver.get(url_tradingview)

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.find_element(By.TAG_NAME, "body")
        )
        time.sleep(2)
        nom_fichier = os.path.join(chemin_enregistrement, f"{actif}.png")
        driver.save_screenshot(nom_fichier)
        print(f"Capture d'écran de la fenêtre pour {actif} enregistrée : {nom_fichier}")
        return nom_fichier
    except WebDriverException as e:
        print(f"Erreur WebDriver lors de la capture d'écran de {actif} : {e}")
        return None
    except Exception as e:
        print(f"Erreur lors de la capture d'écran de {actif} : {e}")
        return None
    finally:
        driver.quit()

# Fonction pour envoyer une image à l'API Gemini et obtenir une réponse
def envoyer_image_a_gemini(chemin_image):
    """
    Envoie une image à l'API Gemini pour analyse.

    Args:
        chemin_image (str): Le chemin du fichier image à envoyer.

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
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare the prompt
        prompt = "Décris cette image et analyse les tendances du marché financier qui y sont visibles."
        
        # Generate the response
        response = model.generate_content([prompt, img])
        
        return response.text
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'image à l'API Gemini : {e}")
        return None

# Boucle principale pour capturer et analyser les actifs
if __name__ == "__main__":
    for actif in actifs:
        chemin_screenshot = prendre_screenshot_tradingview(actif)
        if chemin_screenshot:
            reponse_gemini = envoyer_image_a_gemini(chemin_screenshot)
            os.remove(chemin_screenshot)
            if reponse_gemini:
                print(f"Analyse de Gemini pour {actif}:")
                print(reponse_gemini)
            else:
                print("Aucune analyse disponible dans la réponse de Gemini.")
        time.sleep(10)
    print("Script terminé.")
