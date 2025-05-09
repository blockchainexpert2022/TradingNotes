!pip install selenium pillow requests google-generativeai tenacity
!apt-get update
!apt-get install -y chromium-chromedriver

import requests
import time
import os
import io
from PIL import Image
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException as SeleniumTimeoutException
import glob
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import re # Pour le parsing

# --- CRUCIAL: Clear potential proxy settings ---
proxy_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
for var_name in proxy_vars_to_clear:
    if var_name in os.environ:
        print(f"Clearing environment variable: {var_name}")
        del os.environ[var_name]
os.environ['NO_PROXY'] = '*'
# --- END CRUCIAL SECTION ---

# Configuration
actifs = ["EURUSD"] # Actif principal à trader
CONTEXT_ASSETS = ["TVC:DXY"] # Actifs de contexte comme le DXY
timeframes_init = ["60", "240", "1D", "1W"] # Timeframes pour l'analyse initiale (H1, H4, D1, W1)
timeframes_monitor = ["1", "5", "15"] # Timeframes pour le monitoring (M1, M5, M15)

# --- API KEY MANAGEMENT ---
# REMPLACEZ "VOTRE_CLE_API_GEMINI_ICI" PAR VOTRE VRAIE CLÉ API GEMINI
gemini_api_key = "VOTRE_CLE_API_GEMINI_ICI" # EXEMPLE

if not gemini_api_key or "VOTRE_CLE_API_GEMINI_ICI" in gemini_api_key or "AIzaSyB" not in gemini_api_key:
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
    options.add_argument("--window-size=1920,1200")
    options.binary_location = "/usr/bin/chromium-browser"

    driver = None
    try:
        print(f"Initializing Chrome WebDriver for {actif} {timeframe}...")
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print(f"WebDriverException during Chrome initialization for {actif} {timeframe}: {e}")
        return None
    except Exception as e:
        print(f"Generic error initializing Chrome browser for {actif} {timeframe}: {e}")
        return None

    tv_timeframe = timeframe
    if timeframe == "1D": tv_timeframe = "D"
    elif timeframe == "1W": tv_timeframe = "W"

    url_actif = actif.replace(":", "%3A") # Encoder ':' pour l'URL
    url = f"https://www.tradingview.com/chart/?symbol={url_actif}&interval={tv_timeframe}"
    print(f"Navigating to: {url}")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error navigating to URL {url}: {e}")
        if driver: driver.quit()
        return None

    nom_fichier = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_{int(time.time())}.png")

    try:
        WebDriverWait(driver, 45).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.chart-markup-table, div.tv-chart"))
        )
        print(f"Chart container found for {actif} {timeframe}. Waiting for elements to settle...")
        time.sleep(15) # Laisser temps pour chargement et popups

        popups_selectors = [
            "button[aria-label='Close']", "button[aria-label='Fermer']",
            "div[class*='popup'] button[class*='close']", "button#onetrust-accept-btn-handler",
            "button.tv-dialog__close", "button[data-name='accept-all-cookies']"
        ]
        for selector in popups_selectors:
            try:
                close_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for close_button in close_buttons:
                    if close_button.is_displayed() and close_button.is_enabled():
                        print(f"Attempting to close popup with selector: {selector} for {actif}")
                        driver.execute_script("arguments[0].click();", close_button)
                        time.sleep(2)
                        print(f"Clicked popup with selector: {selector} for {actif}")
                        break
            except Exception: # Ignorer si le popup n'est pas trouvé ou erreur de fermeture
                pass

        print(f"Attempting to save screenshot for {actif} {timeframe} to {nom_fichier}")
        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe} saved to {nom_fichier}")
        return nom_fichier
    except SeleniumTimeoutException:
        print(f"Timeout waiting for chart elements for {actif} {timeframe}.")
        # (Sauvegarde HTML pour debug omise pour la concision, mais elle est bonne à garder)
        return None
    except Exception as e:
        print(f"Error capturing screenshot for {actif} {timeframe}: {e}")
        # (Sauvegarde HTML pour debug omise pour la concision)
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
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # ou 'gemini-1.5-pro-latest'
    chat = model.start_chat(history=[])
    return chat

RETRYABLE_GEMINI_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    TimeoutError
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
    reraise=True
)
def send_message_to_gemini_with_retry(chat_session, content_parts, operation_description="Gemini API call"):
    print(f"Attempting to send message for: {operation_description}")
    response = chat_session.send_message(content_parts, request_options={'timeout': 180.0})
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_analyse_initiale(chat, chemins_images_dict, pdf_path=None, primary_asset_symbol=None, context_asset_symbols=None):
    if context_asset_symbols is None: context_asset_symbols = []
    print(f"Sending initial analysis. PDF path: {pdf_path}")
    intro_actifs = f"l'actif principal {primary_asset_symbol}"
    if context_asset_symbols:
        intro_actifs += f" et l'actif de contexte {', '.join(context_asset_symbols)}"

    content_parts = [
        "ANALYSE INITIALE - Vous êtes un expert en analyse technique ICT (Inner Circle Trader) et votre mission est de fournir une analyse approfondie et exploitable.",
        f"Vous allez recevoir des graphiques multi-timeframes (HTF) pour {intro_actifs}: " + ", ".join(timeframes_init) + " et potentiellement un document PDF de référence.",
        "Votre objectif est de préparer le terrain pour identifier une opportunité de trading à haute probabilité sur l'ACTIF PRINCIPAL.",
        "\n**Principes ICT Clés à intégrer IMPÉRATIVEMENT dans votre analyse :**",
        "1.  **Structure du Marché (Market Structure) :** Pour chaque actif (principal et contexte), identifiez les derniers BOS et MSS.",
        "2.  **Points d'Intérêt (POI) :** Pour chaque actif, décrivez les FVG, OB, Breaker/Mitigation Blocks.",
        "3.  **Liquidité :** Identifiez les pools BSL/SSL et IDM pour chaque actif.",
        "4.  **Premium/Discount Arrays :** Évaluez pour chaque actif.",
        "5.  **Confluence des Signaux :** Mettez en évidence.",
        "6.  **ANALYSE DU DXY (si fourni et pertinent) et CORRÉLATION :**",
        "    *   Analysez la structure, les POI, et la liquidité du DXY.",
        "    *   Quel est le biais directionnel probable du DXY ?",
        "    *   **CRUCIAL :** Comment la situation actuelle et les perspectives du DXY influencent-elles l'actif principal ? (Ex: DXY haussier suggère EURUSD baissier, et vice-versa).",
        "    *   Recherchez activement les **SMT (Smart Money Technique) Divergences** entre le DXY et l'actif principal sur les HTF. Signalez toute divergence claire.",
        "\n**Instructions pour l'analyse du PDF (si fourni) :**",
        "Si un document PDF est joint, analysez son contenu et intégrez ses informations clés dans votre évaluation des graphiques et du DXY.",
    ]
    for asset_type, image_paths in chemins_images_dict.items():
        asset_name_display = primary_asset_symbol if asset_type == "primary" else (context_asset_symbols[0] if context_asset_symbols else "context_asset")
        content_parts.append(f"\n--- GRAPHIQUES POUR {asset_name_display.upper()} ({asset_type.upper()}) ---")
        for img_path in image_paths:
            try:
                print(f"Opening image for {asset_name_display}: {img_path}")
                img = Image.open(img_path)
                # Tente d'extraire le timeframe du nom de fichier
                tf_from_filename = "HTF" # Valeur par défaut
                try:
                    parts = os.path.basename(img_path).split('_')
                    # Pour 'EURUSD_60_timestamp.png', tf est à l'index 1
                    # Pour 'TVC_DXY_60_timestamp.png', tf est à l'index 2
                    idx = 2 if asset_name_display.count('_') > 0 or ':' in asset_name_display else 1
                    tf_from_filename = parts[idx]
                except IndexError:
                    pass # Garde la valeur par défaut "HTF"
                content_parts.append(f"\nGraphique {os.path.basename(img_path)} ({asset_name_display}, Timeframe approx. {tf_from_filename}):")
                content_parts.append(img)
            except FileNotFoundError: print(f"ERROR: Image file not found: {img_path}")
            except Exception as e: print(f"Erreur chargement image {img_path}: {e}")

    if pdf_path:
        try:
            print(f"Uploading PDF: {pdf_path}")
            if os.path.exists(pdf_path):
                uploaded_file = genai.upload_file(path=pdf_path)
                content_parts.append("\nDocument de référence (PDF) fourni. Veuillez l'analyser et l'intégrer:")
                content_parts.append(uploaded_file)
                print(f"PDF {pdf_path} uploaded successfully.")
            else: print(f"ERROR: PDF file not found at path: {pdf_path}")
        except Exception as e: print(f"Erreur chargement ou upload PDF {pdf_path}: {e}")

    content_parts.append(f"""
    \n**Format de Réponse Demandé pour l'Analyse Initiale (Focus sur {primary_asset_symbol}):**

    1.  **Analyse du DXY ({', '.join(context_asset_symbols) if context_asset_symbols else 'N/A'}) :**
        *   Biais directionnel HTF du DXY.
        *   Principaux POI et niveaux de liquidité sur le DXY.
        *   Y a-t-il une SMT Divergence entre le DXY et {primary_asset_symbol} sur les HTF ? Si oui, décrivez-la.

    2.  **Synthèse Globale & Biais Directionnel HTF pour {primary_asset_symbol} (Tenant compte du DXY) :**
        *   Order Flow D1/W1 pour {primary_asset_symbol}.
        *   Biais directionnel privilégié pour {primary_asset_symbol} pour la session à venir.
        *   Structure H4/D1 pour {primary_asset_symbol}.

    3.  **Inventaire Détaillé des POI HTF Clés pour {primary_asset_symbol} :**
        *   Listez les 3-5 POI les plus importants (FVG, OB). Précisez type, timeframe, niveau, importance/confluence avec DXY si pertinent.
        *   Principaux niveaux de liquidité (BSL/SSL) pour {primary_asset_symbol}.

    4.  **Scénarios ICT Prospectifs pour {primary_asset_symbol} (Haussier et Baissier) :**
        *   **Scénario A (Principal) :** Condition d'activation sur POI HTF de {primary_asset_symbol}. Confirmation LTF (MSS M5/M15 avec déplacement).
        *   **Scénario B (Alternatif) :** Condition d'activation et confirmation LTF.
        *   Comment le comportement attendu du DXY soutient-il ces scénarios ?

    5.  **Plan de Monitoring pour {primary_asset_symbol} ({", ".join(timeframes_monitor)}) :**
        *   Sur quels POI HTF de {primary_asset_symbol} allez-vous vous concentrer ?
        *   Quels signaux précis (ex: prise de liquidité, MSS M5) constitueraient un déclencheur ?
    """)
    print("Sending initial prompt to Gemini...")
    try:
        response = send_message_to_gemini_with_retry(chat, content_parts, f"Analyse Initiale {primary_asset_symbol} & DXY")
        print("=== ANALYSE INITIALE COMPLETE DE GEMINI ===")
        print(response.text)
        print("==========================================")
        return True
    except RETRYABLE_GEMINI_EXCEPTIONS as e:
        print(f"Error sending message to Gemini for initial analysis after retries: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error sending message to Gemini for initial analysis: {e}")
        return False

def parse_float_from_text(text_value):
    if text_value is None: return None
    try:
        cleaned_text = re.split(r'\s|[(]', str(text_value))[0]
        return float(cleaned_text.replace(',', '.'))
    except ValueError:
        print(f"Warning: Could not parse float from '{text_value}'")
        return None

def extract_trade_parameters(text):
    entry, sl, tp, direction = None, None, None, None
    if "TRADE CONFIRME: LONG" in text.upper(): direction = "LONG"
    elif "TRADE CONFIRME: SHORT" in text.upper(): direction = "SHORT"

    entry_match = re.search(r"(?:NIVEAU D'ENTRÉE PRÉCIS|ENTRÉE)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    sl_match = re.search(r"(?:NIVEAU DE STOP LOSS \(SL\)|SL)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    tp_match = re.search(r"(?:NIVEAU DE TAKE PROFIT \(TP\)|TP)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)

    if entry_match: entry = parse_float_from_text(entry_match.group(1))
    if sl_match: sl = parse_float_from_text(sl_match.group(1))
    if tp_match: tp = parse_float_from_text(tp_match.group(1))

    if direction and entry is not None and sl is not None and tp is not None:
        return {"direction": direction, "entry": entry, "sl": sl, "tp": tp, "status": "OPEN"}
    return None

def extract_trade_management_updates(text, current_trade):
    updates = {"action": "MAINTENIR"}
    new_sl, new_tp = current_trade.get("sl"), current_trade.get("tp")
    
    if re.search(r"CLÔTURER LE TRADE", text, re.IGNORECASE):
        updates["action"] = "CLOTURER"
        reason_match = re.search(r"(?:RAISON|JUSTIFICATION)\s*:\s*(.+)", text, re.IGNORECASE) # Modifié pour inclure JUSTIFICATION
        updates["reason"] = reason_match.group(1).strip() if reason_match else "Suggestion de Gemini"
        return updates

    sl_update_match = re.search(r"(?:NOUVEAU SL|AJUSTER SL(?: À)?)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE) # Modifié pour "SL à"
    tp_update_match = re.search(r"(?:NOUVEAU TP|AJUSTER TP(?: À)?)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE) # Modifié pour "TP à"

    sl_val = parse_float_from_text(sl_update_match.group(1)) if sl_update_match else None
    tp_val = parse_float_from_text(tp_update_match.group(1)) if tp_update_match else None

    if sl_val is not None and sl_val != new_sl:
        updates["new_sl"] = sl_val
        updates["action"] = "AJUSTER"
    if tp_val is not None and tp_val != new_tp:
        updates["new_tp"] = tp_val
        updates["action"] = "AJUSTER"
        
    if updates["action"] == "AJUSTER":
        justification_match = re.search(r"JUSTIFICATION\s*:\s*(.+)", text, re.IGNORECASE)
        updates["justification"] = justification_match.group(1).strip() if justification_match else "Ajustement suggéré par Gemini"
    return updates

def analyser_screenshot_monitoring(chat, chemin_image_primaire, chemin_image_dxy, timeframe_actuel, actif_primaire_symbol, dxy_symbol, active_trade_details=None):
    print(f"Analyzing {timeframe_actuel}m for {actif_primaire_symbol} (DXY context: {dxy_symbol if dxy_symbol else 'N/A'})")
    if active_trade_details and active_trade_details["status"] == "OPEN":
        print(f"  Active trade: {active_trade_details['direction']} {actif_primaire_symbol} @{active_trade_details['entry']:.5f} SL:{active_trade_details['sl']:.5f} TP:{active_trade_details['tp']:.5f}")

    try:
        img_primaire = Image.open(chemin_image_primaire)
        img_dxy = Image.open(chemin_image_dxy) if chemin_image_dxy and os.path.exists(chemin_image_dxy) else None

        prompt_parts = [f"MISE À JOUR GRAPHIQUE : {actif_primaire_symbol} " + (f"ET {dxy_symbol} " if dxy_symbol else "") + f"- TIMEFRAME {timeframe_actuel}m."]
        prompt_parts.append("Référez-vous IMPÉRATIVEMENT à l'analyse initiale HTF et au PDF (si fourni).")

        if active_trade_details and active_trade_details["status"] == "OPEN":
            prompt_parts.extend([
                f"\n**GESTION DE TRADE EN COURS POUR {actif_primaire_symbol} :**",
                f"Trade {active_trade_details['direction']} ouvert à {active_trade_details['entry']:.5f}, SL {active_trade_details['sl']:.5f}, TP {active_trade_details['tp']:.5f}.",
                f"Analysez {actif_primaire_symbol} " + (f"et {dxy_symbol} " if dxy_symbol else "") + f"({timeframe_actuel}m) pour la GESTION :",
                "1. Le prix s'approche-t-il du SL/TP ? L'action des prix actuelle confirme-t-elle ou invalide-t-elle le trade ?",
                "2. Faut-il AJUSTER SL (ex: breakeven, suiveur ICT) ? Si oui, précisez `NOUVEAU SL : [prix]` et `JUSTIFICATION : [explication ICT]`.",
                "3. Faut-il AJUSTER TP ? Si oui, précisez `NOUVEAU TP : [prix]` et `JUSTIFICATION : [explication ICT]`.",
                "4. Faut-il CLÔTURER LE TRADE (invalidation, objectif proche, conditions de marché changées) ? Si oui, précisez `CLÔTURER LE TRADE. RAISON : [explication ICT]`.",
                "5. Si le DXY est fourni, une SMT divergence ou un mouvement fort du DXY impacte-t-il la décision sur le trade de " + actif_primaire_symbol + " ?",
            ])
        else: # Recherche d'une nouvelle entrée
            prompt_parts.extend([
                f"**RECHERCHE D'OPPORTUNITÉ DE TRADE POUR {actif_primaire_symbol} :**",
                f"1. Sur le graphique de {actif_primaire_symbol} ({timeframe_actuel}m) :",
                f"   - Le prix interagit-il avec un POI HTF (FVG, OB, liquidité) de {actif_primaire_symbol} précédemment identifié ?",
                f"   - Y a-t-il une confirmation d'entrée ICT (ex: MSS après prise de liquidité, Déplacement créant FVG, OTE) ?",
                f"2. Sur le graphique du {dxy_symbol} ({timeframe_actuel}m) (si fourni) :",
                f"   - Le mouvement actuel du {dxy_symbol} confirme-t-il (corrélation attendue) ou contredit-il (divergence) l'action des prix sur {actif_primaire_symbol} ?",
                f"   - Y a-t-il une SMT divergence claire entre {dxy_symbol} et {actif_primaire_symbol} sur ce timeframe {timeframe_actuel}m ?",
            ])
        
        prompt_parts.append(f"\nGraphique actuel {actif_primaire_symbol} {timeframe_actuel}m :"); prompt_parts.append(img_primaire)
        if img_dxy:
             prompt_parts.extend([f"\nGraphique actuel {dxy_symbol} {timeframe_actuel}m :", img_dxy])
        elif dxy_symbol: # DXY est configuré mais l'image n'a pas pu être chargée
            prompt_parts.append(f"\nNote: Le graphique {dxy_symbol} {timeframe_actuel}m n'a pas pu être chargé pour cette analyse. Basez-vous sur l'analyse HTF du DXY si disponible.")

        if active_trade_details and active_trade_details["status"] == "OPEN":
            prompt_parts.append(f"""
            \n**Format de Réponse CONCIS pour la GESTION DE TRADE sur {actif_primaire_symbol}:**
            1.  **STATUT DU TRADE :** [TOUJOURS VALIDE / INVALIDÉ / RISQUÉ / OBJECTIF ATTEINT / STOP LOSS ATTEINT] (Soyez direct)
            2.  **ACTION RECOMMANDÉE :**
                *   Si AJUSTER : `AJUSTER TRADE. NOUVEAU SL : [prix]. NOUVEAU TP : [prix]. JUSTIFICATION : [brève explication ICT]`
                *   Si CLÔTURER : `CLÔTURER LE TRADE. RAISON : [ex: SL Atteint à [prix], Invalidation ICT claire, TP imminent]`
                *   Si MAINTENIR : `MAINTENIR TRADE. JUSTIFICATION : [Le trade évolue comme prévu, pas de signaux contraires majeurs]`
            3.  **OBSERVATIONS CLÉS (ICT) :** (Points importants sur le prix, DXY, liquidité, POI LTF pertinents pour la décision)
            """)
        else: # Recherche d'une nouvelle entrée
            prompt_parts.append(f"""
            \n**Format de Réponse CONCIS pour une NOUVELLE ENTRÉE sur {actif_primaire_symbol}:**
            1.  Si une entrée est confirmée MAINTENANT avec un maximum de confirmations ICT :
                `TRADE CONFIRME: [LONG/SHORT] {actif_primaire_symbol}.`
                `NIVEAU D'ENTRÉE PRÉCIS : [prix]`
                `NIVEAU DE STOP LOSS (SL) : [prix]` (Basé sur la protection ICT, ex: sous/au-dessus du swing créant le MSS/FVG)
                `NIVEAU DE TAKE PROFIT (TP) : [prix]` (Basé sur la liquidité opposée, POI HTF, extension Fibo ICT)
                `JUSTIFICATION DU SL/TP : [brève explication ICT pour le placement du SL et du TP]`
                `RAISONNEMENT ICT GLOBAL : [Confluence des signaux LTF avec HTF, confirmation/divergence DXY, etc.]`
            2.  Si une entrée est IMMINENTE ou que les conditions se préparent :
                `ATTENDRE CONFIRMATION {actif_primaire_symbol}.`
                `ÉLÉMENTS SPÉCIFIQUES ATTENDUS :` (Soyez très précis. Ex: 'Attendre test du FVG M15 à X. Si rejeté et DXY montre Y, chercher MSS haussier M1/M5 avec déplacement.')
            3.  Si le scénario envisagé est INVALIDÉ par ce graphique :
                `INVALIDATION DU SCÉNARIO [LONG/SHORT] {actif_primaire_symbol}.`
                `RAISONNEMENT :` (Expliquez pourquoi. Ex: 'Le prix a cassé violemment le support OB H1, DXY confirme la force opposée.')
            4.  Si aucune des situations ci-dessus n'est claire, mais des POIs LTF se forment ou observations notables :
                `OBSERVATION ({actif_primaire_symbol} / {dxy_symbol if dxy_symbol else 'N/A'}) :` (Décrivez les nouveaux POI LTF pertinents, l'état de la corrélation DXY.)
            """)
        
        response = send_message_to_gemini_with_retry(chat, prompt_parts, f"Analyse Monitoring {timeframe_actuel}m {actif_primaire_symbol} (Trade Active: {'Yes' if active_trade_details and active_trade_details['status'] == 'OPEN' else 'No'})")
        print(f"Gemini {timeframe_actuel}m analysis ({actif_primaire_symbol}" + (f" & {dxy_symbol}" if dxy_symbol else "") + f"): {response.text}")
        return response.text
    except FileNotFoundError as e:
        print(f"ERROR: Screenshot file not found for {timeframe_actuel}m analysis: {e}")
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
    chemins_images_init_dict = {"primary": [], "context": []}
    initial_screenshots_ok = True

    primary_asset_to_analyze = actifs[0]
    dxy_asset_to_analyze = CONTEXT_ASSETS[0] if CONTEXT_ASSETS else None

    print(f"\n--- Capturing HTF for Primary Asset: {primary_asset_to_analyze} ---")
    for tf_interval in timeframes_init:
        screenshot_path = prendre_screenshot_tradingview(primary_asset_to_analyze, tf_interval)
        if screenshot_path:
            chemins_images_init_dict["primary"].append(screenshot_path)
        else:
            print(f"ERROR: Failed to capture screenshot for {primary_asset_to_analyze} {tf_interval}. This is critical for initial analysis.")
            initial_screenshots_ok = False
        time.sleep(5)

    if dxy_asset_to_analyze:
        print(f"\n--- Capturing HTF for Context Asset: {dxy_asset_to_analyze} ---")
        for tf_interval in timeframes_init:
            screenshot_path = prendre_screenshot_tradingview(dxy_asset_to_analyze, tf_interval)
            if screenshot_path:
                chemins_images_init_dict["context"].append(screenshot_path)
            else:
                print(f"Warning: Failed to capture screenshot for DXY ({dxy_asset_to_analyze} {tf_interval}). Initial analysis will proceed without this specific DXY HTF chart.")
            time.sleep(5)

    if not initial_screenshots_ok or not chemins_images_init_dict["primary"]:
        print("ERROR: Not all critical initial HTF screenshots for the primary asset were successfully captured. Cannot proceed with initial analysis.")
        exit()

    initial_analysis_successful = envoyer_analyse_initiale(
        chat_session,
        chemins_images_init_dict,
        pdf_file_path,
        primary_asset_symbol=primary_asset_to_analyze,
        context_asset_symbols=[dxy_asset_to_analyze] if dxy_asset_to_analyze else []
    )
    if not initial_analysis_successful:
        print("Exiting due to failure in initial analysis.")
        exit()

    print("Cleaning up initial HTF screenshots...")
    for asset_type in chemins_images_init_dict:
        for img_p in chemins_images_init_dict[asset_type]:
            try:
                if os.path.exists(img_p): os.remove(img_p)
            except Exception as e: print(f"Could not remove initial screenshot {img_p}: {e}")

    active_trade_info = None
    analysis_cycles_count = 0
    max_analysis_cycles = 60 # Peut être ajusté

    print(f"\n--- Starting Monitoring Loop for {primary_asset_to_analyze} (Context: {dxy_asset_to_analyze if dxy_asset_to_analyze else 'None'}) (max {max_analysis_cycles} cycles) ---")

    while analysis_cycles_count < max_analysis_cycles:
        analysis_cycles_count += 1
        current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        trade_status_message = ""
        if active_trade_info and active_trade_info["status"] == "OPEN":
            trade_status_message = f"(MANAGING: {active_trade_info['direction']} {active_trade_info['asset']} E:{active_trade_info['entry']:.5f} SL:{active_trade_info['sl']:.5f} TP:{active_trade_info['tp']:.5f})"
        elif active_trade_info and active_trade_info["status"] != "OPEN": # Trade a été fermé
             trade_status_message = f"(PREVIOUS TRADE {active_trade_info['asset']} CLOSED: {active_trade_info['status']}. LOOKING FOR NEW ENTRY)"
             active_trade_info = None # Réinitialiser pour chercher un nouveau trade

        print(f"\nMonitoring Cycle #{analysis_cycles_count}/{max_analysis_cycles} for {primary_asset_to_analyze} - {current_time_str} {trade_status_message}")

        for tf_monitor in timeframes_monitor:
            if active_trade_info and active_trade_info["status"] != "OPEN": # Assurer la réinitialisation si un trade a été fermé
                active_trade_info = None

            print(f"-- Capturing and analyzing {primary_asset_to_analyze} " + (f"and {dxy_asset_to_analyze} " if dxy_asset_to_analyze else "") + f"{tf_monitor}m screenshot --")
            
            current_screenshot_path_primary = prendre_screenshot_tradingview(primary_asset_to_analyze, tf_monitor)
            time.sleep(3) # Petite pause entre les captures
            current_screenshot_path_dxy = None
            if dxy_asset_to_analyze:
                current_screenshot_path_dxy = prendre_screenshot_tradingview(dxy_asset_to_analyze, tf_monitor)

            if current_screenshot_path_primary:
                analysis_result_text = analyser_screenshot_monitoring(
                    chat_session,
                    current_screenshot_path_primary,
                    current_screenshot_path_dxy,
                    tf_monitor,
                    primary_asset_to_analyze,
                    dxy_asset_to_analyze,
                    active_trade_info # Passe l'état du trade actuel
                )

                if analysis_result_text and "ERROR" not in analysis_result_text.upper():
                    if active_trade_info and active_trade_info["status"] == "OPEN": # Gérer un trade existant
                        updates = extract_trade_management_updates(analysis_result_text, active_trade_info)
                        if updates["action"] == "AJUSTER":
                            prev_sl = active_trade_info["sl"]
                            prev_tp = active_trade_info["tp"]
                            active_trade_info["sl"] = updates.get("new_sl", active_trade_info["sl"])
                            active_trade_info["tp"] = updates.get("new_tp", active_trade_info["tp"])
                            print(f"TRADE UPDATE: {active_trade_info['asset']} SL {prev_sl:.5f}->{active_trade_info['sl']:.5f}, TP {prev_tp:.5f}->{active_trade_info['tp']:.5f}. Justification: {updates.get('justification', 'N/A')}")
                        elif updates["action"] == "CLOTURER":
                            active_trade_info["status"] = f"CLOSED ({updates.get('reason', 'Gemini suggestion')})"
                            print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n=== TRADE CLOSED: {active_trade_info['asset']} - {active_trade_info['status']} ===\nDetails: {analysis_result_text}\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                            # Ne pas 'break' ici, laisser le cycle des timeframes finir au cas où une autre opportunité se présente vite
                        else: # MAINTENIR
                            print(f"TRADE MAINTAINED: {active_trade_info['asset']}. Gemini says: {(analysis_result_text.split('JUSTIFICATION :')[-1].strip() if 'JUSTIFICATION :' in analysis_result_text else analysis_result_text.splitlines()[0])}")
                    
                    elif not active_trade_info: # Chercher un nouveau trade
                        if "TRADE CONFIRME" in analysis_result_text.upper():
                            new_trade = extract_trade_parameters(analysis_result_text)
                            if new_trade:
                                active_trade_info = {"asset": primary_asset_to_analyze, **new_trade}
                                print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n=== NEW TRADE CONFIRMED: {active_trade_info['direction']} {active_trade_info['asset']} ===\nEntry: {active_trade_info['entry']:.5f}, SL: {active_trade_info['sl']:.5f}, TP: {active_trade_info['tp']:.5f}\nFull Reasoning: {analysis_result_text}\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                                # On pourrait 'break' la boucle des tf_monitor ici si on veut agir immédiatement
                                # break 
                            else:
                                print(f"WARNING: 'TRADE CONFIRME' found by Gemini, but parameters (Entry/SL/TP) could not be parsed reliably. Gemini's full response: {analysis_result_text}")
                        # else: # Afficher les observations même sans trade si désiré
                        # print(f"Observation ({tf_monitor}m for {primary_asset_to_analyze}): {analysis_result_text.splitlines()[0] if analysis_result_text else 'No specific feedback.'}")


                # Nettoyage des screenshots de monitoring
                try:
                    if os.path.exists(current_screenshot_path_primary): os.remove(current_screenshot_path_primary)
                    if current_screenshot_path_dxy and os.path.exists(current_screenshot_path_dxy): os.remove(current_screenshot_path_dxy)
                except Exception as e: print(f"Could not remove monitoring screenshot(s): {e}")
            else:
                print(f"Failed to capture {tf_monitor}m screenshot for {primary_asset_to_analyze}. DXY capture status: {'OK' if current_screenshot_path_dxy else ('Failed/Skipped' if dxy_asset_to_analyze else 'Not configured')}")

            # Si un trade vient d'être confirmé, on peut vouloir passer au cycle suivant plus rapidement ou attendre un peu
            if active_trade_info and active_trade_info["status"] == "OPEN" and "NEW TRADE CONFIRMED" in trade_status_message: # Si on vient d'ouvrir un trade
                 pass # Laisser la boucle de timeframe continuer pour une première gestion immédiate

            # Pause entre les timeframes de monitoring (sauf si on vient de finir le cycle)
            if tf_monitor != timeframes_monitor[-1]:
                print(f"Waiting 10 seconds before next monitoring timeframe ({primary_asset_to_analyze})...")
                time.sleep(10)

        # Fin de la boucle des timeframes_monitor (M1, M5, M15)
        if analysis_cycles_count < max_analysis_cycles:
            # Attente plus courte si un trade est actif, plus longue sinon
            wait_inter_cycle = 30 if (active_trade_info and active_trade_info["status"] == "OPEN") else 60
            print(f"--- End of Monitoring Cycle #{analysis_cycles_count}. Waiting {wait_inter_cycle} seconds for next cycle for {primary_asset_to_analyze}... ---")
            time.sleep(wait_inter_cycle)

    # Conclusion
    if active_trade_info and active_trade_info["status"] == "OPEN":
        print(f"\nProcess finished for {primary_asset_to_analyze}: Maximum number of analysis cycles reached. Trade is still OPEN: {active_trade_info}")
    elif analysis_cycles_count >= max_analysis_cycles:
        print(f"\nProcess finished for {primary_asset_to_analyze}: Maximum number of analysis cycles reached. No trade active or last trade was closed.")
    else: # Normalement ne devrait pas être atteint si max_analysis_cycles est la condition de sortie
        print(f"\nProcess finished for {primary_asset_to_analyze}: Loop exited for other reasons.")
