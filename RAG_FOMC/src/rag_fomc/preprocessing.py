"""Nettoyage conservateur : chiffres, négations et fractions sont conservés."""
import re
import unicodedata


def normalize_text(text):
    # NFC évite les conversions agressives des fractions et symboles financiers.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).replace("\u00a0", " ")).strip()


def lexical_tokens(text):
    # Même fonction pour questions et documents ; aucun stopword supprimé.
    return re.findall(r"\d+(?:[.,]\d+)*(?:/\d+)?%?|[^\W\d_]+(?:['’][^\W\d_]+)*|[¼½¾⅛⅜⅝⅞]", text.lower(), re.UNICODE)
