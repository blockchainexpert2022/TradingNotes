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
actifs = ["EURUSD"] # Vous pouvez ajouter d'autres actifs si nécessaire, mais le script est conçu pour en monitorer un à la fois dans la boucle principale
timeframes_init = ["60", "240", "1D", "1W"] # Timeframes pour l'analyse initiale (H1, H4, D1, W1)
timeframes_monitor = ["1", "5", "15"] # Timeframes pour le monitoring (M1, M5, M15)

# --- API KEY MANAGEMENT ---
# REMPLACEZ "VOTRE_CLE_API_GEMINI_ICI" PAR VOTRE VRAIE CLÉ API GEMINI
gemini_api_key = "VOTRE_CLE_API_GEMINI_ICI"

if not gemini_api_key or "VOTRE_CLE_API_GEMINI_ICI" in gemini_api_key or "AIzaSyB" not in gemini_api_key:
    raise ValueError("GEMINI_API_KEY n'est pas définie ou est toujours la valeur par défaut. Veuillez définir votre clé API réelle.")
# --- END API KEY MANAGEMENT ---

chemin_enregistrement = "/tmp/screenshots"
chemin_pdf = "/tmp/pdf" # S'attendra à trouver des PDFs ici s'ils existent
os.makedirs(chemin_enregistrement, exist_ok=True)
os.makedirs(chemin_pdf, exist_ok=True) # Crée le dossier PDF même s'il n'y a pas de PDF

# Configure Gemini
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise

def reset_environnement():
    """Nettoie les dossiers de travail"""
    for folder in [chemin_enregistrement]: # Ne nettoie pas chemin_pdf intentionnellement
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
    print("Screenshot environment reset")

def prendre_screenshot_tradingview(actif, timeframe):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1200")
    options.binary_location = "/usr/bin/chromium-browser" # Assurez-vous que c'est le bon chemin sur Colab

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

    # Convertir les timeframes pour TradingView (ex: 60 -> 60, 240 -> 240, 1D -> D, 1W -> W)
    tv_timeframe = timeframe
    if timeframe == "1D":
        tv_timeframe = "D"
    elif timeframe == "1W":
        tv_timeframe = "W"

    url = f"https://www.tradingview.com/chart/?symbol={actif}&interval={tv_timeframe}"
    print(f"Navigating to: {url}")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error navigating to URL {url}: {e}")
        if driver:
            driver.quit()
        return None

    # Générer un nom de fichier unique avec le timeframe correct
    nom_fichier = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_{int(time.time())}.png")

    try:
        WebDriverWait(driver, 45).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.chart-markup-table, div.tv-chart"))
        )
        print("Chart container found. Waiting for elements to settle...")
        time.sleep(15) # Augmenté pour laisser plus de temps au chargement complet et popups

        popups_selectors = [
            "button[aria-label='Close']",
            "button[aria-label='Fermer']", # Version française
            "div[class*='popup'] button[class*='close']",
            "button#onetrust-accept-btn-handler",
            "button.tv-dialog__close", # Pour certains popups de TradingView
            "button[data-name='accept-all-cookies']" # Autre sélecteur de cookies
        ]
        for selector in popups_selectors:
            try:
                # Attendre un peu que le bouton soit potentiellement cliquable
                close_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for close_button in close_buttons:
                    if close_button.is_displayed() and close_button.is_enabled():
                        print(f"Attempting to close popup with selector: {selector}")
                        driver.execute_script("arguments[0].click();", close_button)
                        time.sleep(2) # Attendre que le popup se ferme
                        print(f"Clicked popup with selector: {selector}")
                        break # On suppose qu'un seul popup de ce type doit être fermé
            except Exception as e_popup:
                # print(f"Popup not found or error closing it with selector {selector}: {e_popup}")
                pass

        # Sauvegarde de la capture d'écran
        print(f"Attempting to save screenshot to {nom_fichier}")
        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe} saved to {nom_fichier}")
        return nom_fichier
    except SeleniumTimeoutException:
        print(f"Timeout waiting for chart elements for {actif} {timeframe}. Page might not have loaded correctly.")
        debug_html_path = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_debug_timeout.html")
        with open(debug_html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Saved page source to {debug_html_path} for debugging.")
        return None
    except Exception as e:
        print(f"Error capturing screenshot for {actif} {timeframe}: {e}")
        # Sauvegarder le HTML de la page pour débogage en cas d'erreur inattendue
        debug_html_path = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_debug_error.html")
        try:
            with open(debug_html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Saved page source to {debug_html_path} for debugging.")
        except:
             print(f"Could not save page source for debugging.")
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
        print(f"Found PDF: {pdfs[0]}") # Prend le premier PDF trouvé
        return pdfs[0]
    else:
        print(f"No PDF found in {chemin_pdf}")
        return None

def initialiser_session_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # ou 'gemini-1.5-pro-latest' pour potentiellement de meilleurs résultats (plus cher)
    chat = model.start_chat(history=[])
    return chat

RETRYABLE_GEMINI_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    # google.api_core.exceptions.DeadlineExceeded, # Décommentez si vous utilisez gRPC et rencontrez ces erreurs
    # google.api_core.exceptions.ServiceUnavailable,
    # google.generativeai.types.generation_types.StopCandidateException, # Seulement si vous savez que c'est transitoire
    TimeoutError # Erreur Python générique pour les timeouts
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
    reraise=True
)
def send_message_to_gemini_with_retry(chat_session, content_parts, operation_description="Gemini API call"):
    print(f"Attempting to send message for: {operation_description}")
    response = chat_session.send_message(content_parts, request_options={'timeout': 180.0}) # Timeout de 3 minutes par tentative
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_analyse_initiale(chat, chemins_images, pdf_path=None):
    print(f"Sending initial analysis. PDF path: {pdf_path}")
    content_parts = [
        "ANALYSE INITIALE - Vous êtes un expert en analyse technique ICT (Inner Circle Trader) et votre mission est de fournir une analyse approfondie et exploitable.",
        "Vous allez recevoir des graphiques multi-timeframes (HTF) : " + ", ".join(timeframes_init) + " et potentiellement un document PDF de référence.",
        "Votre objectif est de préparer le terrain pour identifier une opportunité de trading à haute probabilité.",
        "\n**Principes ICT Clés à intégrer IMPÉRATIVEMENT dans votre analyse :**",
        "1.  **Structure du Marché (Market Structure) :** Identifiez les derniers Breaks of Structure (BOS) significatifs et les Market Structure Shifts (MSS) potentiels sur chaque HTF. Précisez leur direction (haussière/baissière).",
        "2.  **Points d'Intérêt (POI) - C'est ici que le 'traçage' textuel est crucial :**",
        "    *   **Fair Value Gaps (FVG) :** Pour chaque FVG pertinent, décrivez son emplacement approximatif (ex: 'FVG haussier entre 1.0850 et 1.0870'), le timeframe sur lequel il est le plus clair, et s'il est en zone Premium ou Discount par rapport au range pertinent.",
        "    *   **Order Blocks (OB) :** Pour chaque OB pertinent (bullish/bearish), décrivez son emplacement approximatif (ex: 'Order Block baissier H4 entre 1.0900 et 1.0915'), le timeframe, et s'il a initié un BOS.",
        "    *   **Breaker Blocks / Mitigation Blocks :** Si évidents, identifiez-les de la même manière.",
        "3.  **Liquidité :** Identifiez les pools de liquidité clairs (Buy-side Liquidity - BSL, Sell-side Liquidity - SSL) et les zones d'Inducement (IDM) sur les HTF.",
        "4.  **Premium/Discount Arrays :** Évaluez si le prix se situe actuellement dans une zone de Premium (pour vendre) ou Discount (pour acheter) par rapport aux swings majeurs récents sur les HTF pertinents (surtout D1/H4).",
        "5.  **Confluence des Signaux :** Mettez en évidence les zones où plusieurs signaux ICT convergent (ex: un FVG H4 dans un OB D1, proche d'un niveau de liquidité).",
        "\n**Instructions pour l'analyse du PDF (si fourni) :**",
        "Si un document PDF est joint, analysez son contenu et intégrez ses informations clés (ex: règles spécifiques, contextes économiques, analyses antérieures) dans votre évaluation des graphiques. Expliquez comment le contenu du PDF influence votre interprétation des POIs ou des scénarios.",
    ]

    for img_path in chemins_images:
        try:
            print(f"Opening image: {img_path}")
            img = Image.open(img_path)
            # Essayer d'extraire le timeframe du nom de fichier pour plus de clarté dans le prompt
            try:
                tf_from_filename = os.path.basename(img_path).split('_')[1] # e.g., EURUSD_60_timestamp.png -> 60
            except:
                tf_from_filename = "HTF" # Fallback
            content_parts.append(f"\nGraphique {os.path.basename(img_path)} (Timeframe approx. {tf_from_filename}):")
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
                # Gérer l'upload avec retry pourrait être une bonne idée ici aussi si cela échoue souvent
                uploaded_file = genai.upload_file(path=pdf_path)
                content_parts.append("\nDocument de référence (PDF) fourni. Veuillez l'analyser et l'intégrer:")
                content_parts.append(uploaded_file)
                print(f"PDF {pdf_path} uploaded successfully.")
            else:
                print(f"ERROR: PDF file not found at path: {pdf_path}")
        except Exception as e:
            print(f"Erreur chargement ou upload PDF {pdf_path}: {e}")

    content_parts.append(f"""
    \n**Format de Réponse Demandé pour l'Analyse Initiale :**

    1.  **Synthèse Globale & Biais Directionnel HTF :**
        *   Quel est le flux d'ordres (Order Flow) principal sur les timeframes D1 et W1 ?
        *   Quel est le biais directionnel privilégié (haussier/baissier) pour la session à venir, basé sur l'analyse des graphiques ({", ".join(timeframes_init)}) et du PDF (si fourni) ?
        *   Décrivez la structure de marché actuelle sur H4 et D1 (ex: 'tendance haussière avec BOS récents, actuellement en retracement').

    2.  **Inventaire Détaillé des POI HTF Clés (FVG, OB, Liquidité) :**
        *   Listez les 3-5 POI les plus importants (FVG, OB) sur les graphiques HTF. Pour chacun, précisez :
            *   Type de POI (ex: FVG Haussier, OB Baissier).
            *   Timeframe (ex: H4, D1).
            *   Niveau de prix approximatif (ex: 'zone 1.1234 - 1.1256').
            *   Importance/Confluence (ex: 'FVG H1 aligné avec OB H4 en zone Discount').
        *   Listez les principaux niveaux de liquidité (BSL/SSL) à surveiller.

    3.  **Scénarios ICT Prospectifs (Haussier et Baissier) :**
        *   **Scénario A (Principal) :** Décrivez le scénario de trading ICT le plus probable.
            *   Condition d'activation : Quelle réaction attendez-vous sur quel POI HTF ? (ex: 'Mitigation du FVG H4 à 1.0850').
            *   Confirmation LTF recherchée : Quel pattern sur M1/M5/M15 validerait ce scénario ? (ex: 'MSS sur M5 avec déplacement laissant un FVG dans la direction du trade').
        *   **Scénario B (Alternatif) :** Décrivez un second scénario plausible si le premier est invalidé.
            *   Condition d'activation et confirmation LTF.

    4.  **Plan de Monitoring pour les Timeframes Inférieurs ({", ".join(timeframes_monitor)}) :**
        *   Sur quels POI HTF spécifiques (identifiés au point 2) allez-vous concentrer votre attention lorsque vous recevrez les graphiques M1, M5, M15 ?
        *   Quels signaux précis (ex: 'prise de liquidité sous l'OB H1 puis réintégration avec MSS M5') constitueraient un déclencheur d'entrée en accord avec vos scénarios ?
    """)
    print("Sending initial prompt to Gemini...")
    try:
        response = send_message_to_gemini_with_retry(chat, content_parts, "Analyse Initiale")
        print("=== ANALYSE INITIALE COMPLETE DE GEMINI ===")
        print(response.text)
        print("==========================================")
        print(f"=== DEBUT DU MONITORING ({', '.join(tf + 'm' for tf in timeframes_monitor)}) ===")
        return True # Indiquer le succès
    except RETRYABLE_GEMINI_EXCEPTIONS as e:
        print(f"Error sending message to Gemini for initial analysis after retries: {e}")
        if hasattr(e, 'response') and e.response: print(f"Gemini API response (error): {e.response}")
        print("CRITICAL: Initial analysis failed. Cannot proceed with monitoring effectively.")
        return False
    except Exception as e:
        print(f"Unexpected error sending message to Gemini for initial analysis: {e}")
        if hasattr(e, 'response') and e.response: print(f"Gemini API response (error): {e.response}")
        print("CRITICAL: Initial analysis failed. Cannot proceed with monitoring effectively.")
        return False

def analyser_screenshot_monitoring(chat, chemin_image, timeframe_actuel):
    print(f"Analyzing {timeframe_actuel}m screenshot: {chemin_image}")
    try:
        img = Image.open(chemin_image)
        prompt_parts = [
            f"MISE À JOUR GRAPHIQUE : {timeframe_actuel} MINUTE(S).",
            "Référez-vous IMPÉRATIVEMENT à l'analyse initiale HTF (biais, POIs HTF, scénarios) et au PDF (si fourni) pour contextualiser ce graphique.",
            f"Le prix interagit-il avec un POI HTF (FVG, OB, liquidité) précédemment identifié ? Si oui, lequel et comment ?",
            f"Sur ce graphique {timeframe_actuel}m, recherchez des confirmations d'entrée précises ou des invalidations des scénarios ICT.",
            "Concentrez-vous sur :",
            "   - Market Structure Shift (MSS) sur ce timeframe, idéalement après une prise de liquidité ou une mitigation d'un POI HTF.",
            "   - Déplacement (Displacement) créant un nouveau FVG sur ce timeframe dans la direction du trade anticipé.",
            "   - Formation d'un Optimal Trade Entry (OTE) après une réaction à un POI HTF.",
            "\n**Format de Réponse CONCIS et PRÉCIS :**",
            "1.  Si une entrée est confirmée MAINTENANT :",
            "    `TRADE CONFIRME: [LONG/SHORT] à [NIVEAU DE PRIX D'ENTRÉE APPROXIMATIF SUR CE GRAPHIQUE] sur [TIMEFRAME DE CONFIRMATION (1m, 5m, ou 15m)].`",
            "    `RAISONNEMENT ICT :` (Expliquez la confluence de signaux : ex: 'MSS M5 après mitigation FVG H4 à 1.1230, avec FVG M5 créé par déplacement à 1.1240-1.1245. Stop loss estimé sous [niveau]. Objectif [niveau]').",
            "2.  Si une entrée est IMMINENTE ou que les conditions se préparent :",
            "    `ATTENDRE CONFIRMATION.`",
            "    `ÉLÉMENTS SPÉCIFIQUES ATTENDUS :` (Soyez très précis. Ex: 'Attendre test du FVG M15 à 1.0880-1.0875. Si rejeté, chercher MSS haussier sur M1 ou M5 avec déplacement. Ou: 'Attendre prise de liquidité sous le plus bas récent à 1.0865 puis réintégration au-dessus de 1.0870 avec confirmation LTF').",
            "3.  Si le scénario envisagé est INVALIDÉ par ce graphique :",
            "    `INVALIDATION DU SCÉNARIO [LONG/SHORT].`",
            "    `RAISONNEMENT :` (Expliquez pourquoi. Ex: 'Le prix a cassé violemment le support OB H1 à 1.2300 sans réaction, invalidant le scénario long. Nouveau biais baissier potentiel si MSS confirmé sous ce niveau').",
            "4.  Si aucune des situations ci-dessus n'est claire, mais des POIs LTF se forment :",
            "    `OBSERVATION :` (Décrivez les nouveaux POI LTF pertinents. Ex: 'Nouveau FVG baissier M15 formé à 1.0950-1.0960. Le prix s'approche de la zone de liquidité SSL HTF.').",
            f"\nGraphique actuel {timeframe_actuel}m :",
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
        if hasattr(e, 'response') and e.response: print(f"Gemini API response (error details): {e.response}")
        return f"Error during {timeframe_actuel}m analysis: {e}"

# --- Main Execution Block ---
if __name__ == "__main__":
    reset_environnement()

    pdf_file_path = trouver_pdfs() # Recherche un PDF dans /tmp/pdf
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
    for actif_symbol in actifs: # Pour l'instant, on ne gère qu'un actif à la fois pour la suite du monitoring
        for tf_interval in timeframes_init:
            screenshot_path = prendre_screenshot_tradingview(actif_symbol, tf_interval)
            if screenshot_path:
                chemins_images_init.append(screenshot_path)
            else:
                print(f"Failed to capture screenshot for {actif_symbol} {tf_interval}. This might impact initial analysis.")
                initial_screenshots_ok = False # On peut décider si c'est critique
            time.sleep(5)

    if not chemins_images_init or not initial_screenshots_ok:
        print("ERROR: Not all initial HTF screenshots were successfully captured. Cannot proceed with initial analysis.")
        exit()

    initial_analysis_successful = envoyer_analyse_initiale(chat_session, chemins_images_init, pdf_file_path)
    if not initial_analysis_successful:
        print("Exiting due to failure in initial analysis.")
        exit()

    print("Cleaning up initial HTF screenshots...")
    for img_p in chemins_images_init:
        try:
            if os.path.exists(img_p):
                os.remove(img_p)
        except Exception as e:
            print(f"Could not remove initial screenshot {img_p}: {e}")

    trade_signal_confirmed = False
    analysis_cycles_count = 0
    max_analysis_cycles = 20 # Nombre de cycles de monitoring avant de s'arrêter

    print(f"\n--- Starting Monitoring Loop ({', '.join(tf + 'm' for tf in timeframes_monitor)}) (max {max_analysis_cycles} cycles) ---")

    # Le script actuel monitore le premier actif de la liste `actifs`
    actif_to_monitor = actifs[0]

    while not trade_signal_confirmed and analysis_cycles_count < max_analysis_cycles:
        analysis_cycles_count += 1
        current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"\nMonitoring Cycle #{analysis_cycles_count}/{max_analysis_cycles} for {actif_to_monitor} - {current_time_str}")

        for tf_monitor_interval in timeframes_monitor:
            print(f"-- Capturing and analyzing {actif_to_monitor} {tf_monitor_interval}m screenshot --")
            current_screenshot_path = prendre_screenshot_tradingview(actif_to_monitor, tf_monitor_interval)

            if current_screenshot_path:
                analysis_result_text = analyser_screenshot_monitoring(chat_session, current_screenshot_path, tf_monitor_interval)

                if analysis_result_text:
                    if "TRADE CONFIRME" in analysis_result_text.upper():
                        trade_signal_confirmed = True
                        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        print("=== TRADE CONFIRMÉ PAR GEMINI ===")
                        print(analysis_result_text)
                        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        break # Sortir de la boucle des timeframes_monitor

                    elif "ERROR" in analysis_result_text.upper():
                         print(f"Note: Analysis for {tf_monitor_interval}m returned an error message: {analysis_result_text}")
                else:
                    print(f"Warning: No analysis result text returned for {tf_monitor_interval}m.")

                try:
                    if os.path.exists(current_screenshot_path):
                        os.remove(current_screenshot_path)
                except Exception as e:
                    print(f"Could not remove {tf_monitor_interval}m screenshot {current_screenshot_path}: {e}")
            else:
                print(f"Failed to capture {tf_monitor_interval}m screenshot for {actif_to_monitor}. Will try next timeframe or cycle.")

            if trade_signal_confirmed:
                break # Sortir de la boucle des timeframes si un trade est confirmé

            print(f"Waiting 10 seconds before next monitoring timeframe ({actif_to_monitor})...")
            time.sleep(10) # Attente entre les captures de différents timeframes de monitoring

        if trade_signal_confirmed:
            break # Sortir de la boucle principale des cycles si un trade est confirmé

        if analysis_cycles_count < max_analysis_cycles:
            print(f"--- End of Monitoring Cycle #{analysis_cycles_count}. Waiting 60 seconds for next cycle for {actif_to_monitor}... ---")
            time.sleep(60) # Attente avant le prochain cycle complet de monitoring

    # Conclusion
    if trade_signal_confirmed:
        print(f"\nProcess finished for {actif_to_monitor}: Trade signal confirmed and analyzed.")
    elif analysis_cycles_count >= max_analysis_cycles:
        print(f"\nProcess finished for {actif_to_monitor}: Maximum number of analysis cycles reached without trade confirmation.")
    else:
        print(f"\nProcess finished for {actif_to_monitor}: Loop exited for other reasons.")
