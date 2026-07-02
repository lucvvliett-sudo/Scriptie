# Landelijk snellaadprobleem

## Over dit project

Deze repository bevat de Python-code die is ontwikkeld voor mijn bachelorscriptie Wiskunde aan de Radboud Universiteit.

Het doel van het project is het bepalen van optimale locaties voor snellaadstations in Nederland met behulp van een logic-based Benders-decompositie.

## Inhoud

De repository bestaat uit de volgende onderdelen:

- `src/` bevat alle Python-code.
- `data/` bevat de gemeentegraaf die als invoer wordt gebruikt en de requirements.txt waar de python pakketten in staan.

## Benodigde Python-pakketten

- networkx
- pulp
- matplotlib
- requests
- shapely
- cbsodata
- itertools
- os
- math

Deze kunnen geïnstalleerd worden door middel van 
conda forge -r requirements.txt

het kan zijn dat cbsodata hier op vastloopt, gebruik dan voor cbsodata
pip install -r cbsodata==1.3.5
