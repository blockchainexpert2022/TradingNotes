!pip install selenium pillow requests google-generativeai tenacity
!apt-get update
!apt-get install -y chromium-chromedriver

import requests
import time
import os
import io
from PIL import Image
# import base64 # Non utilisé, peut être supprimé
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC # Pour des attentes plus explicites
import shutil
from selenium.common.exceptions import WebDriverException, TimeoutException as SeleniumTimeoutException
import glob
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- CRUCIAL: Clear potential proxy settings ---
# S'assurer que cela est exécuté très tôt.
proxy_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
for var_name in proxy_vars_to_clear:
    if var_name in os.environ:
        print(f"Clearing environment variable: {var_name}")
        del os.environ[var_name]
# Forcer requests à ne pas utiliser de proxies (si google-generativeai l'utilise en interne)
os.environ['NO_PROXY'] = '*' # Pourrait aider à forcer la non-utilisation de proxy
# --- END CRUCIAL SECTION ---

# Configuration
actifs = ["EURUSD"]
timeframes_init = ["60", "240", "1D", "1W"]
timeframes_monitor = ["1", "5", "15"]

# --- API KEY MANAGEMENT ---
gemini_api_key = "REPLACE_ME" # REMPLACEZ PAR VOTRE VRAIE CLÉ

if not gemini_api_key or "VOTRE_CLE_API_GEMINI_ICI" in gemini_api_key or "AIzaSyB" not in gemini_api_key: # Added a basic check for placeholder
    raise ValueError("GEMINI_API_KEY n'est pas définie ou est toujours la valeur par défaut. Veuillez définir votre clé API réelle.")
# --- END API KEY MANAGEMENT ---

chemin_enregistrement = "/tmp/screenshots"
chemin_pdf = "/tmp/pdf"
os.makedirs(chemin_enregistrement, exist_ok=True)
os.makedirs(chemin_pdf, exist_ok=True)

# Configure Gemini
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise

def reset_environnement():
    """Nettoie les dossiers de travail"""
    for folder in [chemin_enregistrement]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
    print("Screenshot environment reset")

def prendre_screenshot_tradingview(actif, timeframe):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1200") # Légèrement plus haut pour potentiels popups en bas
    options.binary_location = "/usr/bin/chromium-browser" # Assurez-vous que c'est le bon chemin

    driver = None
    try:
        print("Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=options)
        print("WebDriver initialized.")
    except WebDriverException as e:
        print(f"WebDriverException during Chrome initialization: {e}")
        if "net::ERR_NAME_NOT_RESOLVED" in str(e) or "dns" in str(e).lower():
            print("DNS resolution error. Check network connectivity in Colab environment.")
        return None
    except Exception as e:
        print(f"Generic error initializing Chrome browser: {e}")
        return None

    url = f"https://www.tradingview.com/chart/?symbol={actif}&interval={timeframe}"
    print(f"Navigating to: {url}")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error navigating to URL {url}: {e}")
        if driver:
            driver.quit()
        return None


    nom_fichier = os.path.join(chemin_enregistrement, f"{actif}_{timeframe}m_{int(time.time())}.png")
    try:
        # Attendre que le conteneur principal du graphique soit présent
        WebDriverWait(driver, 45).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.chart-markup-table, div.tv-chart"))
        )
        print("Chart container found. Waiting for elements to settle...")
        time.sleep(10) # Augmenté pour laisser plus de temps au chargement complet et popups

        # Essayer de fermer les pop-ups connus (fenêtre de cookie, etc.)
        popups_selectors = [
            "button[aria-label='Close']", # Bouton générique de fermeture
            "div[class*='popup'] button[class*='close']", # Autre style de bouton de fermeture de popup
            "button#onetrust-accept-btn-handler" # Bouton d'acceptation des cookies
        ]
        for selector in popups_selectors:
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, selector)
                if close_button.is_displayed() and close_button.is_enabled():
                    print(f"Attempting to close popup with selector: {selector}")
                    driver.execute_script("arguments[0].click();", close_button) # JS click peut être plus robuste
                    time.sleep(2) # Attendre que le popup se ferme
            except:
                pass # L'élément n'est pas là, on continue

        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe}m saved to {nom_fichier}")
        return nom_fichier
    except SeleniumTimeoutException:
        print(f"Timeout waiting for chart elements for {actif} {timeframe}m. Page might not have loaded correctly.")
        # Sauvegarder le HTML de la page pour débogage
        debug_html_path = os.path.join(chemin_enregistrement, f"{actif}_{timeframe}m_debug_timeout.html")
        with open(debug_html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Saved page source to {debug_html_path} for debugging.")
        return None
    except Exception as e:
        print(f"Error capturing screenshot for {actif} {timeframe}m: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def trouver_pdfs():
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
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    chat = model.start_chat(history=[])
    return chat

# Définir les exceptions pour lesquelles Tenacity doit réessayer
RETRYABLE_GEMINI_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    # google.api_core.exceptions.DeadlineExceeded, # Si Gemini utilise gRPC et que cette erreur apparaît
    # google.api_core.exceptions.ServiceUnavailable, # Idem
    # google.generativeai.types.generation_types.StopCandidateException, # Si c'est une erreur transitoire
    # Pour les erreurs spécifiques que vous avez vues
    # Attention: HTTPConnectionPool est souvent de urllib3, utilisé par requests.
    # On capture les erreurs de requests qui devraient les encapsuler.
    # TimeoutError est très générique, mais dans ce contexte, c'est probablement réseau.
    TimeoutError
)


@retry(
    stop=stop_after_attempt(3),  # Réessayer 3 fois maximum (total de 4 tentatives)
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Attendre 4s, puis 8s, puis 10s (exponentiel plafonné)
    retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
    reraise=True # Si toutes les tentatives échouent, relancer l'exception originale
)
def send_message_to_gemini_with_retry(chat_session, content_parts, operation_description="Gemini API call"):
    """Envoie un message à Gemini avec une politique de retry."""
    print(f"Attempting to send message for: {operation_description}")
    # Note: Le timeout ici est pour une seule tentative.
    # La doc de google-generativeai indique que le timeout par défaut est de 60s.
    # Vous pouvez le surcharger si nécessaire : response = chat.send_message(content_parts, request_options={'timeout': 120})
    # Le timeout de 600s vu dans votre erreur était peut-être pour le pool de connexion, pas la requête elle-même.
    response = chat_session.send_message(content_parts, request_options={'timeout': 180.0}) # Timeout de 3 minutes par tentative
    print(f"Successfully sent message for: {operation_description}")
    return response


def envoyer_analyse_initiale(chat, chemins_images, pdf_path=None):
    print(f"Sending initial analysis. PDF path: {pdf_path}")
    content_parts = [
        "ANALYSE INITIALE - Vous êtes un expert en analyse technique ICT (Inner Circle Trader). ",
        "Analysez ces graphiques multi-timeframes (HTF) et le document PDF fourni (si disponible). Préparez-vous à recevoir des mises à jour des graphiques 1 minute, 5 minutes et 15 minutes pour chercher une entrée.",
        "Timeframes fournis pour l'analyse initiale (HTF): " + ", ".join(timeframes_init) + ".",
        "Principes clés de l'analyse ICT à considérer:",
        "1. Structure du marché (Market Structure Shifts, Breaks of Structure).",
        "2. Points d'intérêt (POI) : Fair Value Gaps (FVG), Order Blocks (OB), Breaker Blocks, Mitigation Blocks.",
        "3. Liquidité : Inducement, Liquidity Sweeps (Buy-side/Sell-side liquidity).",
        "4. Temps et Prix (Time & Price Theory) : Killzones (London, New York), Optimal Trade Entry (OTE).",
        "5. Confluence des signaux sur plusieurs timeframes."
    ]

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

    uploaded_file = None
    if pdf_path:
        try:
            print(f"Uploading PDF: {pdf_path}")
            if os.path.exists(pdf_path):
                # La fonction d'upload de fichier peut aussi avoir des timeouts ou erreurs réseau
                # Pour l'instant, on ne la met pas dans une boucle de retry, mais ça pourrait être nécessaire
                uploaded_file = genai.upload_file(path=pdf_path)
                content_parts.append("\nDocument de référence (PDF) fourni. Veuillez le considérer dans votre analyse:")
                content_parts.append(uploaded_file)
            else:
                print(f"ERROR: PDF file not found at path: {pdf_path}")
        except Exception as e:
            print(f"Erreur chargement ou upload PDF {pdf_path}: {e}") # Peut aussi être une erreur réseau

    content_parts.append("""
    \nBasé sur les graphiques HTF et le PDF (si fourni), veuillez fournir une analyse initiale complète:
    1.  **Synthèse Multi-Timeframe (HTF):** Quel est le biais directionnel général basé sur les timeframes supérieurs (60m, 240m, 1D, 1W)? Identifiez la structure clé.
    2.  **Niveaux Clés et POI (sur HTF):** Marquez les Fair Value Gaps (FVG), Order Blocks, et zones de liquidité importants sur les graphiques HTF fournis.
    3.  **Scénarios ICT Potentiels (basés sur HTF):** Décrivez 1 ou 2 scénarios de trading ICT plausibles (long ou short) basés sur l'analyse HTF. Mentionnez les conditions qui valideraient ces scénarios.
    4.  **Préparation pour le Monitoring (1m, 5m, 15m):** Quels éléments spécifiques allez-vous rechercher sur les graphiques 1m, 5m, et 15m pour confirmer une entrée basée sur l'analyse des timeframes supérieurs et le PDF?
    """)

    print("Sending initial prompt to Gemini...")
    try:
        response = send_message_to_gemini_with_retry(chat, content_parts, "Analyse Initiale")
        print("=== ANALYSE INITIALE COMPLETE DE GEMINI ===")
        print(response.text)
        print("==========================================")
        print(f"=== DEBUT DU MONITORING ({', '.join(tf + 'm' for tf in timeframes_monitor)}) ===")
    except RETRYABLE_GEMINI_EXCEPTIONS as e: # Attrape les exceptions après que les retries aient échoué
        print(f"Error sending message to Gemini for initial analysis after retries: {e}")
        if hasattr(e, 'response') and e.response: print(f"Gemini API response (error): {e.response}")
        print("CRITICAL: Initial analysis failed. Cannot proceed with monitoring effectively.")
        # Décidez si vous voulez quitter ou continuer avec un monitoring "aveugle"
        # exit() # ou return False / raise Exception
    except Exception as e: # Autres erreurs non prévues par les retries
        print(f"Unexpected error sending message to Gemini for initial analysis: {e}")
        if hasattr(e, 'response') and e.response: print(f"Gemini API response (error): {e.response}")
        print("CRITICAL: Initial analysis failed. Cannot proceed with monitoring effectively.")
        # exit()

def analyser_screenshot_monitoring(chat, chemin_image, timeframe_actuel):
    print(f"Analyzing {timeframe_actuel}m screenshot: {chemin_image}")
    try:
        img = Image.open(chemin_image)
        prompt_parts = [
            f"MISE A JOUR GRAPHIQUE {timeframe_actuel} MINUTE(S).",
            "Analysez ce nouveau graphique en gardant à l'esprit l'analyse initiale multi-timeframe (HTF) et le contenu du PDF (si fourni).",
            "Recherchez une confirmation d'entrée ICT (comme un Market Structure Shift dans un POI HTF, remplissage d'un FVG HTF, OTE après une prise de liquidité sur un niveau HTF).",
            f"Le graphique actuel est en {timeframe_actuel} minute(s).",
            "Répondez CONCISEMENT avec:",
            "1. 'TRADE CONFIRME: [LONG/SHORT] à [NIVEAU APPROXIMATIF] sur [TIMEFRAME DE CONFIRMATION]' si tous les critères d'une entrée ICT sont remplis MAINTENANT. Expliquez brièvement la confirmation et le timeframe sur lequel elle est la plus claire (1m, 5m, ou 15m).",
            "2. 'ATTENDRE' si une entrée n'est pas encore claire sur ce timeframe. Listez les éléments spécifiques que vous attendez de voir pour une confirmation (ex: 'ATTENDRE sur 5m: Rejet d'un FVG H1 à 1.2345 et MSS sur M5').",
            "3. 'INVALIDATION' si le scénario précédent est invalidé par ce graphique.",
            f"Niveaux clés actuels sur ce graphique {timeframe_actuel}m (FVG, liquidité proche):",
            img
        ]
        response = send_message_to_gemini_with_retry(chat, prompt_parts, f"Analyse Monitoring {timeframe_actuel}m")
        print(f"Gemini {timeframe_actuel}m analysis: {response.text}")
        return response.text
    except FileNotFoundError:
        print(f"ERROR: {timeframe_actuel}m screenshot file not found: {chemin_image}")
        return f"ERROR: Screenshot file not found for {timeframe_actuel}m."
    except RETRYABLE_GEMINI_EXCEPTIONS as e:
        print(f"Erreur réseau/timeout persistante pour analyse screenshot {timeframe_actuel}m après retries: {e}")
        return f"Error during {timeframe_actuel}m analysis after retries: {e}"
    except Exception as e:
        print(f"Erreur inattendue analyse screenshot {timeframe_actuel}m: {e}")
        # Ici, vous pourriez vouloir logger plus de détails sur `e` si c'est une erreur Gemini spécifique
        if hasattr(e, 'response') and e.response: print(f"Gemini API response (error details): {e.response}")
        return f"Error during {timeframe_actuel}m analysis: {e}"


# --- Main Execution Block ---
if __name__ == "__main__":
    reset_environnement()

    pdf_file_path = trouver_pdfs()
    if not pdf_file_path:
        print("WARNING: No PDF found. Proceeding without PDF reference.")

    print("Initializing Gemini session...")
    try:
        chat_session = initialiser_session_gemini()
    except Exception as e:
        print(f"Failed to initialize Gemini session: {e}. Exiting.")
        exit()


    print("Capturing initial timeframe screenshots (HTF)...")
    chemins_images_init = []
    initial_screenshots_ok = True
    for actif_symbol in actifs:
        for tf_interval in timeframes_init:
            screenshot_path = prendre_screenshot_tradingview(actif_symbol, tf_interval)
            if screenshot_path:
                chemins_images_init.append(screenshot_path)
            else:
                print(f"Failed to capture screenshot for {actif_symbol} {tf_interval}. This might impact initial analysis.")
                # Vous pourriez décider de rendre cela fatal ou non
                # initial_screenshots_ok = False # Décommentez si un échec ici doit arrêter le script
            time.sleep(5) # Augmenté pour plus de stabilité

    if not chemins_images_init: # or not initial_screenshots_ok:
        print("ERROR: No initial HTF screenshots were successfully captured. Cannot proceed with initial analysis.")
        exit()

    envoyer_analyse_initiale(chat_session, chemins_images_init, pdf_file_path)
    # Si envoyer_analyse_initiale échoue de manière critique, elle pourrait appeler exit() ou lever une exception.
    # Vous pouvez ajouter ici une vérification si elle retourne une valeur indiquant le succès/échec.

    print("Cleaning up initial HTF screenshots...")
    for img_p in chemins_images_init:
        try:
            if os.path.exists(img_p):
                os.remove(img_p)
        except Exception as e:
            print(f"Could not remove initial screenshot {img_p}: {e}")

    trade_signal_confirmed = False
    analysis_cycles_count = 0
    max_analysis_cycles = 20

    print(f"\n--- Starting Monitoring Loop ({', '.join(tf + 'm' for tf in timeframes_monitor)}) (max {max_analysis_cycles} cycles) ---")

    while not trade_signal_confirmed and analysis_cycles_count < max_analysis_cycles:
        analysis_cycles_count += 1
        current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"\nMonitoring Cycle #{analysis_cycles_count}/{max_analysis_cycles} - {current_time_str}")

        actif_to_monitor = actifs[0]

        for tf_monitor_interval in timeframes_monitor:
            print(f"-- Capturing and analyzing {tf_monitor_interval}m screenshot --")
            current_screenshot_path = prendre_screenshot_tradingview(actif_to_monitor, tf_monitor_interval)

            if current_screenshot_path:
                analysis_result_text = analyser_screenshot_monitoring(chat_session, current_screenshot_path, tf_monitor_interval)

                if analysis_result_text: # Vérifier si on a eu un résultat (même un message d'erreur formaté)
                    if "TRADE CONFIRME" in analysis_result_text.upper(): # .upper() pour être insensible à la casse
                        trade_signal_confirmed = True
                        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        print("=== TRADE CONFIRMÉ PAR GEMINI ===")
                        print(analysis_result_text)
                        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        break # Sortir de la boucle des timeframes_monitor

                    # Si l'analyse a échoué (contient "ERROR:" ou similaire), on le logue mais on continue
                    elif "ERROR" in analysis_result_text.upper():
                         print(f"Note: Analysis for {tf_monitor_interval}m returned an error message: {analysis_result_text}")
                else:
                    # Cela ne devrait pas arriver si analyser_screenshot_monitoring retourne toujours une chaîne
                    print(f"Warning: No analysis result text returned for {tf_monitor_interval}m.")


                try:
                    if os.path.exists(current_screenshot_path):
                        os.remove(current_screenshot_path)
                except Exception as e:
                    print(f"Could not remove {tf_monitor_interval}m screenshot {current_screenshot_path}: {e}")
            else:
                print(f"Failed to capture {tf_monitor_interval}m screenshot. Will try next timeframe or cycle.")

            if trade_signal_confirmed:
                break

            time.sleep(5)

        if trade_signal_confirmed:
            break

        print(f"--- End of Monitoring Cycle #{analysis_cycles_count}. Waiting 60 seconds for next cycle... ---")
        time.sleep(60)

    # Conclusion
    if trade_signal_confirmed:
        print("\nProcess finished: Trade signal confirmed and analyzed.")
    elif analysis_cycles_count >= max_analysis_cycles:
        print("\nProcess finished: Maximum number of analysis cycles reached without trade confirmation.")
    else:
        print("\nProcess finished: Loop exited for other reasons (e.g., critical error during setup, or an unhandled break).")
