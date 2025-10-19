
Concepts fondamentaux de l'action des prix (price action) dictée par un algorithme.

### **1. Les Outils Fondamentaux du Débutant**

Pour commencer, un trader n'a besoin que de très peu d'outils :

*   **Unités de Temps (Timeframes) :** Se concentrer **uniquement** sur trois unités de temps :
    *   15 minutes (M15)
    *   5 minutes (M5)
    *   1 minute (M1)
    *   Il insiste sur le fait qu'aucun autre timeframe (ni journalier, ni horaire, ni en secondes) n'est nécessaire au début.

*   **Concepts Clés à Observer :**
    1.  **Liquidité (Liquidity) :** L'objectif principal de l'algorithme. Elle se trouve au-dessus des anciens plus hauts et en dessous des anciens plus bas. L'attention est portée sur les **"Relative Equal Highs"** (plus hauts égaux) et **"Relative Equal Lows"** (plus bas égaux). Ce sont des zones de prix "lisses" où les ordres (stop-loss, ordres d'entrée) s'accumulent.
        *   **Astuce d'identification :** Un "relative equal high" a une très haute probabilité d'être visé si le sommet de gauche est **légèrement plus haut** que celui de droite. L'inverse est vrai pour les "relative equal lows".
    2.  **Inefficacités (Inefficiencies) :** Ce sont les zones de déséquilibre dans le prix, principalement les **Fair Value Gaps (FVG)**. L'algorithme cherche également à revenir combler ces zones. ICT les nomme "Siby" (Sell-side Imbalance, Buy-side Inefficiency) ou "Bisy" (Buy-side Imbalance, Sell-side Inefficiency).
    3.  **Déplacement (Displacement) :** Un mouvement de prix fort, rapide et agressif qui montre une intention claire. Ce mouvement laisse souvent des FVG dans son sillage.

### **2. Le Modèle de Trading de Base ("The Baseline")**

La stratégie initiale n'est pas de prédire toute la journée, mais d'identifier où le marché est susceptible d'aller à court terme (le **"Draw on Liquidity"**).

Le scénario de base décrit est le suivant :
1.  **Prise de Liquidité :** Le marché descend sous un ancien plus bas ("relative equal lows") pour y prendre la liquidité.
2.  **Rupture de Structure avec Déplacement :** Immédiatement après, le marché se retourne violemment à la hausse, cassant un sommet à court terme. C'est le "Displacement".
3.  **Création de Zones d'Intérêt :** Ce mouvement crée des zones clés pour un potentiel re-test :
    *   Un **Order Block** haussier (la dernière bougie baissière avant le mouvement haussier).
    *   Un **Bullish Breaker** (les bougies haussières qui formaient le sommet précédent, juste avant la chute qui a pris la liquidité).
4.  **Entrée et Cible :** Le trader attend un retour du prix dans l'une de ces zones (Order Block, Breaker, ou FVG créé par le déplacement) pour viser la liquidité située au-dessus, c'est-à-dire les **"Relative Equal Highs"** qui n'ont pas encore été touchés.

### **3. L'Élément le Plus Important : Le Temps (Time)**

Toute cette mécanique est synchronisée sur des fenêtres temporelles très précises, basées sur **l'heure de New York (Eastern Time)**.

*   **Fenêtre d'Analyse (8h00 - 8h30) :** S'asseoir devant les graphiques pour identifier où se trouvent les zones de liquidité "lisses" (equal highs/lows) et les inefficacités sur les graphiques M15, M5 et M1.
*   **Fenêtre d'Action (à partir de 8h30 et 9h30) :** Les setups ont une forte probabilité de se former après l'ouverture de la session de New York. L'algorithme est conçu pour "chercher et détruire" la liquidité ou combler les inefficacités pendant ces périodes.

### **4. Méthodologie d'Apprentissage (Pour un Débutant)**

L'accent n'est pas mis sur le trading immédiat, mais sur l'étude et le journaling.
1.  **Ne pas trader au début :** Simplement observer et documenter.
2.  **Prendre des captures d'écran :** Chaque fois qu'un de ces scénarios se produit, il faut le capturer.
3.  **Annoter :** Noter combien de temps le mouvement a pris, combien de bougies, et surtout, **ce que vous avez ressenti** en l'observant (anxiété, impatience, confiance, etc.).
4.  **Commencer petit :** Lorsqu'on se sent prêt à trader, il faut utiliser **un seul micro-contrat**. L'objectif est de se désensibiliser à la peur et à l'avidité, ce qui est impossible si la taille de la position est trop grande.

En résumé, la technique consiste à utiliser le **temps** pour anticiper une chasse à la **liquidité**. Il faut identifier les zones de prix "lisses" (equal highs/lows), attendre que le marché piège un côté (par exemple, en prenant les plus bas), puis chercher un point d'entrée sur un retracement (vers un FVG, Order Block ou Breaker) pour viser le côté opposé.
