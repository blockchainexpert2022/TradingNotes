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

# --- CRUCIAL: Clear potential proxy settings ---
# Do this at the very beginning of your script execution,
# especially before any network libraries like genai or requests are configured or used.
proxy_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
for var_name in proxy_vars_to_clear:
    if var_name in os.environ:
        print(f"Clearing environment variable: {var_name}")
        del os.environ[var_name]
# --- END CRUCIAL SECTION ---

# Configuration
actifs = ["EURUSD"]
timeframes_init = ["1", "5", "15", "60", "240", "1D", "1W"]  # Pour analyse initiale
timeframe_monitor = "1"  # Pour monitoring en boucle

# --- API KEY MANAGEMENT ---
# BEST PRACTICE for Colab: Use Colab Secrets (key icon on the left panel)
# from google.colab import userdata
# gemini_api_key = userdata.get('GEMINI_API_KEY_NAME_YOU_SET') # Replace with your secret name

# For quick testing (less secure, visible in notebook):
gemini_api_key = "REPLACE_ME" # AIzaSy... is a placeholder, replace with your actual key

if not gemini_api_key or gemini_api_key == "YOUR_GEMINI_API_KEY": # Check if it's the placeholder
    raise ValueError("GEMINI_API_KEY is not set or is still the placeholder. Please set your actual API key.")
# --- END API KEY MANAGEMENT ---

chemin_enregistrement = "/tmp/screenshots"
chemin_pdf = "/tmp/pdf" # Make sure your PDF is in this directory
os.makedirs(chemin_enregistrement, exist_ok=True)
os.makedirs(chemin_pdf, exist_ok=True) # Creates if not exists, does nothing if it does

# Configure Gemini (AFTER clearing proxies and setting API key)
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise # Stop execution if Gemini can't be configured

def reset_environnement():
    """Nettoie les dossiers de travail"""
    # Only cleans screenshots, PDF is expected to be manually placed or handled elsewhere
    for folder in [chemin_enregistrement]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder) # Recreate after deleting
    print("Screenshot environment reset")

# reset_environnement() # Call this only if you want to clear screenshots at the start

def prendre_screenshot_tradingview(actif, timeframe):
    """Capture un screenshot pour un actif et timeframe donné"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # For Colab, explicitly set the binary location for chromium
    options.binary_location = "/usr/bin/chromium-browser"

    driver = None # Initialize driver to None for the finally block
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        # This can happen if chromedriver/chromium is not installed correctly or paths are wrong
        print(f"WebDriverException during Chrome initialization: {e}")
        print("Ensure chromium-chromedriver is installed and paths are correct.")
        return None
    except Exception as e:
        print(f"Generic error initializing Chrome browser: {e}")
        return None

    url = f"https://www.tradingview.com/chart/?symbol={actif}&interval={timeframe}" # Use www for english if fr is an issue
    print(f"Navigating to: {url}")
    driver.get(url)

    nom_fichier = os.path.join(chemin_enregistrement, f"{actif}_{timeframe}_{int(time.time())}.png")
    try:
        # Wait for a common element, e.g., the chart container or body
        # Adjust selector if needed
        WebDriverWait(driver, 30).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "div.chart-markup-table") or d.find_element(By.TAG_NAME, "body")
        )
        # Add a slight delay for elements to finish rendering after page load signal
        time.sleep(7) # Increased wait time

        # Potentially close pop-ups if they appear
        try:
            # Example: Look for a common close button class or ID if TradingView has persistent pop-ups
            close_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
            if close_button.is_displayed():
                close_button.click()
                time.sleep(1) # Wait for pop-up to close
        except:
            pass # No pop-up or not found, continue

        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe} saved to {nom_fichier}")
        return nom_fichier
    except Exception as e:
        print(f"Error capturing screenshot for {actif} {timeframe}: {e}")
        # driver.save_screenshot(os.path.join(chemin_enregistrement, f"error_{actif}_{timeframe}.png")) # Save error screenshot
        # print(driver.page_source) # Print page source for debugging
        return None
    finally:
        if driver:
            driver.quit()

def trouver_pdfs():
    """Retourne le premier PDF trouvé dans le dossier /tmp/pdf"""
    if not os.path.exists(chemin_pdf):
        print(f"PDF directory not found: {chemin_pdf}")
        return None
    pdfs = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
    if pdfs:
        print(f"Found PDF: {pdfs[0]}")
        return pdfs[0]
    else:
        print(f"No PDF found in {chemin_pdf}")
        return None

def initialiser_session_gemini():
    """Initialise une session Gemini avec contexte"""
    # Use a more capable model if needed, but 1.5-flash is good for multi-turn chat
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Using -latest can be beneficial
    chat = model.start_chat(history=[]) # Start with an empty history
    return chat

def envoyer_analyse_initiale(chat, chemins_images, pdf_path=None): # Renamed for clarity
    """Envoie l'analyse initiale avec tous les timeframes"""
    print(f"Sending initial analysis. PDF path: {pdf_path}")
    content_parts = [ # Changed to content_parts for clarity with model.generate_content
        "ANALYSE INITIALE - Vous êtes un expert en analyse technique ICT (Inner Circle Trader). ",
        "Analysez ces graphiques multi-timeframes et le document PDF fourni (si disponible). Préparez-vous à recevoir des mises à jour du graphique 1 minute.",
        "Timeframes fournis pour l'analyse initiale: " + ", ".join(timeframes_init) + ".",
        "Principes clés de l'analyse ICT à considérer:",
        "1. Structure du marché (Market Structure Shifts, Breaks of Structure).",
        "2. Points d'intérêt (POI) : Fair Value Gaps (FVG), Order Blocks (OB), Breaker Blocks, Mitigation Blocks.",
        "3. Liquidité : Inducement, Liquidity Sweeps (Buy-side/Sell-side liquidity).",
        "4. Temps et Prix (Time & Price Theory) : Killzones (London, New York), Optimal Trade Entry (OTE).",
        "5. Confluence des signaux sur plusieurs timeframes."
    ]

    # Ajouter les images
    for img_path in chemins_images:
        try:
            print(f"Opening image: {img_path}")
            img = Image.open(img_path)
            content_parts.append(f"\nGraphique {os.path.basename(img_path)}:")
            content_parts.append(img)
        except FileNotFoundError:
            print(f"ERROR: Image file not found: {img_path}")
        except Exception as e:
            print(f"Erreur chargement image {img_path}: {e}")

    # Ajouter le PDF si disponible
    uploaded_file = None
    if pdf_path:
        try:
            print(f"Uploading PDF: {pdf_path}")
            # Ensure the file exists before attempting to upload
            if os.path.exists(pdf_path):
                uploaded_file = genai.upload_file(path=pdf_path) # Use path= for clarity
                content_parts.append("\nDocument de référence (PDF) fourni. Veuillez le considérer dans votre analyse:")
                content_parts.append(uploaded_file) # Add the File object
            else:
                print(f"ERROR: PDF file not found at path: {pdf_path}")
        except Exception as e:
            print(f"Erreur chargement ou upload PDF {pdf_path}: {e}")
            # Potentially log more details about the error, e.g., e.args

    content_parts.append("""
    \nBasé sur les graphiques et le PDF (si fourni), veuillez fournir une analyse initiale complète:
    1.  **Synthèse Multi-Timeframe:** Quel est le biais directionnel général basé sur les timeframes supérieurs? Identifiez la structure clé.
    2.  **Niveaux Clés et POI:** Marquez les Fair Value Gaps (FVG), Order Blocks, et zones de liquidité importants sur les graphiques fournis.
    3.  **Scénarios ICT Potentiels:** Décrivez 1 ou 2 scénarios de trading ICT plausibles (long ou short) basés sur l'analyse actuelle. Mentionnez les conditions qui valideraient ces scénarios.
    4.  **Préparation pour le Monitoring 1m:** Quels éléments spécifiques allez-vous rechercher sur le graphique 1 minute pour confirmer une entrée basée sur l'analyse des timeframes supérieurs et le PDF?
    """)

    print("Sending initial prompt to Gemini...")
    try:
        response = chat.send_message(content_parts) # Send the list of parts
        print("=== ANALYSE INITIALE COMPLETE DE GEMINI ===")
        print(response.text)
        print("==========================================")
        print("=== DEBUT DU MONITORING 1m ===")
        # return response.text # Not strictly needed to return if just printing
    except Exception as e:
        print(f"Error sending message to Gemini for initial analysis: {e}")
        # You might want to see the parts of the response that did come through if it's a streaming error or partial error
        if hasattr(e, 'response') and e.response:
            print(f"Gemini API response (error): {e.response}")

    # Clean up uploaded file if it was created
    # This is important to avoid hitting quota limits if you upload many files
    # However, if you need to refer to this PDF in subsequent turns *by its uploaded reference*, don't delete it yet.
    # For chat.send_message, the context is maintained, so the model *should* remember the PDF.
    # If you were making a new model.generate_content call each time, you'd need to re-send or cache the File object.
    # For now, let's assume chat context handles it. If issues arise, one might need to manage uploaded files more explicitly.
    # if uploaded_file:
    #     try:
    #         print(f"Deleting uploaded file: {uploaded_file.name}")
    #         genai.delete_file(uploaded_file.name)
    #     except Exception as e:
    #         print(f"Error deleting uploaded file {uploaded_file.name}: {e}")


def analyser_screenshot_1m(chat, chemin_image):
    """Analyse un screenshot 1m dans le contexte existant"""
    print(f"Analyzing 1m screenshot: {chemin_image}")
    try:
        img = Image.open(chemin_image)
        prompt = [ # Using a list for multi-part message
            "MISE A JOUR GRAPHIQUE 1 MINUTE.",
            "Analysez ce nouveau graphique 1 minute en gardant à l'esprit l'analyse initiale multi-timeframe et le contenu du PDF (si fourni).",
            "Recherchez une confirmation d'entrée ICT (comme un Market Structure Shift dans un POI, remplissage d'un FVG, OTE après une prise de liquidité).",
            "Répondez CONCISEMENT avec:",
            "1. 'TRADE CONFIRME: [LONG/SHORT] à [NIVEAU APPROXIMATIF]' si tous les critères d'une entrée ICT sont remplis MAINTENANT. Expliquez brièvement la confirmation.",
            "2. 'ATTENDRE' si une entrée n'est pas encore claire. Listez les éléments spécifiques que vous attendez de voir pour une confirmation (ex: 'ATTENDRE: Rejet d'un FVG H1 à 1.2345 et MSS sur M1').",
            "3. 'INVALIDATION' si le scénario précédent est invalidé.",
            "Niveaux clés actuels sur ce graphique 1m (FVG, liquidité proche):",
            img # The PIL Image object
        ]
        response = chat.send_message(prompt)
        print(f"Gemini 1m analysis: {response.text}")
        return response.text
    except FileNotFoundError:
        print(f"ERROR: 1m screenshot file not found: {chemin_image}")
        return "ERROR: Screenshot file not found."
    except Exception as e:
        print(f"Erreur analyse screenshot 1m: {e}")
        return f"Error during 1m analysis: {e}"

# --- Main Execution Block ---
if __name__ == "__main__":
    # 0. Reset screenshot directory (optional, useful for clean runs)
    reset_environnement()

    # 1. Find PDF
    pdf_file_path = trouver_pdfs() # Renamed for clarity
    if not pdf_file_path:
        print("WARNING: No PDF found. Proceeding without PDF reference.")
        # Decide if you want to halt execution if PDF is mandatory
        # exit("ERROR: PDF document is required for analysis.")

    # 2. Initialize Gemini Chat Session
    print("Initializing Gemini session...")
    chat_session = initialiser_session_gemini()

    # 3. Capture Initial Screenshots
    print("Capturing initial timeframe screenshots...")
    chemins_images_init = []
    for actif_symbol in actifs: # Renamed for clarity
        for tf_interval in timeframes_init: # Renamed for clarity
            screenshot_path = prendre_screenshot_tradingview(actif_symbol, tf_interval)
            if screenshot_path:
                chemins_images_init.append(screenshot_path)
            else:
                print(f"Failed to capture screenshot for {actif_symbol} {tf_interval}. Skipping.")
            time.sleep(3) # Pause to avoid overwhelming TradingView or getting rate-limited

    if not chemins_images_init:
        print("ERROR: No initial screenshots were captured. Cannot proceed with initial analysis.")
        exit() # Or handle this more gracefully

    # 4. Send Initial Analysis to Gemini
    envoyer_analyse_initiale(chat_session, chemins_images_init, pdf_file_path)

    # 5. Clean up initial screenshots (optional)
    print("Cleaning up initial screenshots...")
    for img_p in chemins_images_init:
        try:
            if os.path.exists(img_p):
                os.remove(img_p)
        except Exception as e:
            print(f"Could not remove initial screenshot {img_p}: {e}")

    # 6. Monitoring Loop for 1m Timeframe
    trade_confirmed = False # Renamed for clarity
    analyses_count = 0 # Renamed for clarity
    max_analyses_allowed = 60 # e.g., 1 hour of 1-minute candles

    print(f"\n--- Starting 1m Monitoring Loop (max {max_analyses_allowed} attempts) ---")
    while not trade_confirmed and analyses_count < max_analyses_allowed:
        analyses_count += 1
        current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"\nMonitoring 1m - Analysis #{analyses_count}/{max_analyses_allowed} - {current_time_str}")

        # For simplicity, assuming one asset from 'actifs' list for monitoring
        # If multiple assets, you'd need to decide which one to monitor or loop through them
        actif_to_monitor = actifs[0]

        current_screenshot_path = prendre_screenshot_tradingview(actif_to_monitor, timeframe_monitor)

        if current_screenshot_path:
            analysis_result_text = analyser_screenshot_1m(chat_session, current_screenshot_path)

            if analysis_result_text:
                # Simple check for "TRADE CONFIRME" (case-insensitive)
                if "TRADE CONFIRME" in analysis_result_text.upper():
                    trade_confirmed = True
                    print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    print("=== TRADE CONFIRMÉ PAR GEMINI ===")
                    print(analysis_result_text) # Print the confirmation details
                    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    break # Exit the while loop

            # Clean up the 1m screenshot
            try:
                if os.path.exists(current_screenshot_path):
                    os.remove(current_screenshot_path)
            except Exception as e:
                print(f"Could not remove 1m screenshot {current_screenshot_path}: {e}")

            # Wait before next analysis
            print("Waiting 60 seconds for the next 1m candle...")
            time.sleep(60)
        else:
            print("Failed to capture 1m screenshot. Retrying in 30 seconds...")
            time.sleep(30) # Shorter wait if capture failed, then retry loop

    # 7. Conclusion
    if trade_confirmed:
        print("\nProcess finished: Trade signal confirmed and analyzed.")
    elif analyses_count >= max_analyses_allowed:
        print("\nProcess finished: Maximum number of analyses reached without trade confirmation.")
    else:
        print("\nProcess finished: Loop exited for other reasons (e.g. error).")

