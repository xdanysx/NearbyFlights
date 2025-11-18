# AirplaneRadar

Diese App zeigt mithilfe der OpenSky-API welche Flüge sich in einem bestimmten Punkt befinden und welche momentanen eigenschaften haben wie Flughöhe und Fluggeschwindigkeit, Richtung etc.

Um den Längen- & Breitengrad sowie den Radius und die Ergebnisanzahl zu verändern muss die .txt-Datei in ./data/config.txt die Variablen verändert werden.

Kurze erklärung: Nearby flights (OpenSky) — interaktiver Modus:
- Einmalig: zeige die nächsten N Flugzeuge
- Laufend : scanne im Intervall und zeige jeweils das nächstgelegene Flugzeug
Konfiguration erfolgt interaktiv beim Start.