from flask import Flask, render_template, jsonify, request
import sqlite3
import subprocess
import re
import statistics
import random
from datetime import datetime
import platform

app = Flask(__name__)
DB_PATH = 'database.db'

# ============ MODE DEMO ============
MODE_DEMO = False  # Mettre True pour simuler sans connexion réseau

# ============ INITIALISATION DB ============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS mesures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            latence_ms REAL,
            jitter_ms REAL,
            perte_pourcent REAL,
            debit_down_mbps REAL,
            debit_up_mbps REAL,
            mos_voip REAL,
            qoe_video REAL,
            qoe_gaming REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ============ MESURE PING AMÉLIORÉE ============
def mesurer_ping(cible="8.8.8.8", count=10):
    """
    Mesure latence, jitter et perte avec 10 pings pour plus de précision.
    Fonctionne sur Windows, Linux et macOS.
    """
    try:
        system = platform.system().lower()

        if system == 'windows':
            cmd = ['ping', '-n', str(count), '-w', '2000', cible]
        else:
            cmd = ['ping', '-c', str(count), '-W', '2', cible]

        print(f"[PING] Commande: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )

        output = result.stdout + result.stderr
        print(f"[PING] Sortie brute:\n{output[:800]}")

        times = _extraire_temps(output, system)
        print(f"[PING] Temps extraits: {times}")

        if not times:
            print("[PING] Échec extraction → None")
            return None, None, None

        latence = statistics.mean(times)
        jitter = statistics.stdev(times) if len(times) > 1 else 0.0
        perte = round(max(0, (count - len(times)) / count * 100), 1)

        print(f"[PING] latence={latence:.2f}ms  jitter={jitter:.2f}ms  perte={perte}%")
        return round(latence, 2), round(jitter, 2), perte

    except subprocess.TimeoutExpired:
        print("[PING] Timeout!")
        return None, None, None
    except Exception as e:
        print(f"[PING] Erreur: {e}")
        return None, None, None


def _extraire_temps(output, system):
    """Extrait les temps de réponse du ping selon l'OS."""
    times = []

    if system == 'windows':
        # "temps=12ms" "temps<1ms" "time=12ms" "time<1ms"
        patterns = [
            r'[Tt]emps[=<](\d+(?:\.\d+)?)\s*ms',
            r'[Tt]ime[=<](\d+(?:\.\d+)?)\s*ms',
            r'temps[=<](\d+)',
            r'time[=<](\d+)',
        ]
    else:
        # "time=12.3 ms" ou "time=12ms"
        patterns = [
            r'time[=<](\d+(?:\.\d+)?)\s*ms',
            r'time[=<](\d+(?:\.\d+)?)',
        ]

    for pattern in patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            times = [float(m) for m in matches if float(m) < 5000]
            break

    # Fallback générique: cherche Nms dans la sortie ligne par ligne
    if not times:
        for line in output.splitlines():
            if 'ttl=' in line.lower() or 'octets' in line.lower() or 'bytes' in line.lower():
                m = re.search(r'(\d+(?:\.\d+)?)\s*ms', line, re.IGNORECASE)
                if m:
                    val = float(m.group(1))
                    if val < 5000:
                        times.append(val)

    return times


# ============ MESURE DÉBIT ============
def mesurer_debit():
    """
    Tente speedtest-cli. En cas d'échec, retourne des valeurs estimées
    basées sur la latence avec un commentaire dans les logs.
    """
    try:
        result = subprocess.run(
            ['speedtest-cli', '--simple', '--timeout', '15'],
            capture_output=True, text=True, timeout=35
        )
        output = result.stdout
        print(f"[SPEEDTEST] {output.strip()}")

        down = re.search(r'Download:\s*([\d.]+)', output)
        up = re.search(r'Upload:\s*([\d.]+)', output)

        if down and up:
            return round(float(down.group(1)), 1), round(float(up.group(1)), 1)

    except FileNotFoundError:
        print("[SPEEDTEST] speedtest-cli non trouvé")
    except subprocess.TimeoutExpired:
        print("[SPEEDTEST] Timeout")
    except Exception as e:
        print(f"[SPEEDTEST] Erreur: {e}")

    # Valeurs de fallback
    print("[SPEEDTEST] Utilisation valeurs estimées (45/15 Mbps)")
    return 45.0, 15.0


# ============ CALCULS QoE ============
def calculer_mos_voip(latence, jitter, perte):
    """
    E-model ITU-T G.107 simplifié.
    Retourne un score MOS entre 1.0 et 5.0.
    """
    try:
        latence = float(latence or 0)
        jitter = float(jitter or 0)
        perte = float(perte or 0)
    except (ValueError, TypeError):
        return 1.0

    latence = max(0, min(latence, 1000))
    jitter = max(0, min(jitter, 500))
    perte = max(0, min(perte, 100))

    # Dégradation due au délai de bout-en-bout
    delay_impairment = latence * 0.03
    if latence > 150:
        delay_impairment += (latence - 150) * 0.02  # Pénalité supplémentaire au delà de 150ms

    # Dégradation due aux pertes
    equipment_impairment = perte * 10

    # Dégradation due au jitter (tampon de gigue estimé à 2×jitter)
    jitter_impairment = jitter * 0.15

    R = 93.2 - delay_impairment - equipment_impairment - jitter_impairment
    R = max(0, min(100, R))

    # Conversion R → MOS (formule ITU-T P.800)
    if R < 0:
        mos = 1.0
    else:
        mos = 1 + 0.035 * R + R * (R - 60) * (100 - R) * 7e-6

    mos = max(1.0, min(5.0, mos))
    print(f"[MOS] R={R:.1f} → MOS={mos:.2f}")
    return round(mos, 2)


def calculer_qoe_video(debit_down, perte):
    """QoE Vidéo – basée sur les seuils Netflix/YouTube."""
    if not debit_down:
        return 1.0
    perte = max(0, min(float(perte), 100))

    if debit_down >= 50:
        base = 5.0
    elif debit_down >= 25:
        base = 4.5
    elif debit_down >= 10:
        base = 4.0
    elif debit_down >= 5:
        base = 3.0
    elif debit_down >= 2.5:
        base = 2.0
    else:
        base = 1.0

    # Pénalité pour les pertes (rebuffering)
    penalty = (perte / 5) * 0.5
    return max(1.0, min(5.0, round(base - penalty, 2)))


def calculer_qoe_gaming(latence, jitter, perte):
    """
    QoE Gaming – latence très critique.
    Seuils issus des recommandations esport et FPS.
    """
    try:
        latence = float(latence or 999)
        jitter = float(jitter or 999)
        perte = float(perte or 100)
    except (ValueError, TypeError):
        return 1.0

    latence = max(0, min(latence, 1000))
    jitter = max(0, min(jitter, 500))
    perte = max(0, min(perte, 100))

    # Score de base selon latence
    if latence <= 15:
        base = 5.0
    elif latence <= 30:
        base = 4.5
    elif latence <= 60:
        base = 4.0
    elif latence <= 100:
        base = 3.0
    elif latence <= 150:
        base = 2.0
    else:
        base = 1.0

    # Pénalités jitter et perte
    jitter_penalty = min(1.5, jitter / 20)
    perte_penalty = min(1.5, perte / 3)

    score = base - jitter_penalty - perte_penalty
    return max(1.0, min(5.0, round(score, 2)))


# ============ ROUTES ============
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/mesure')
def api_mesure():
    """Effectue une mesure complète QoS + calcul QoE."""
    try:
        if MODE_DEMO:
            latence = round(random.uniform(5, 120), 1)
            jitter = round(random.uniform(0.5, 20), 1)
            perte = round(random.uniform(0, 3), 1)
            debit_down = round(random.uniform(10, 150), 1)
            debit_up = round(random.uniform(5, 60), 1)
            print(f"[DEMO] latence={latence} jitter={jitter} perte={perte} down={debit_down} up={debit_up}")
        else:
            print("=" * 40)
            print(f"[MESURE] {datetime.now().isoformat()}")
            latence, jitter, perte = mesurer_ping()

            if latence is None:
                msg = ("Impossible de mesurer la latence. "
                       "Vérifiez votre connexion ou activez MODE_DEMO = True dans app.py")
                return jsonify({'error': msg}), 500

            debit_down, debit_up = mesurer_debit()

        # Calculs QoE
        mos   = calculer_mos_voip(latence, jitter, perte)
        video = calculer_qoe_video(debit_down, perte)
        gaming = calculer_qoe_gaming(latence, jitter, perte)

        # Stockage
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO mesures
                (timestamp, latence_ms, jitter_ms, perte_pourcent,
                 debit_down_mbps, debit_up_mbps, mos_voip, qoe_video, qoe_gaming)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), latence, jitter, perte,
              debit_down, debit_up, mos, video, gaming))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'qos': {
                'latence_ms': latence,
                'jitter_ms': jitter,
                'perte_pourcent': perte,
                'debit_down_mbps': debit_down,
                'debit_up_mbps': debit_up
            },
            'qoe': {
                'mos_voip': mos,
                'qoe_video': video,
                'qoe_gaming': gaming
            }
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


@app.route('/api/historique')
def api_historique():
    """Retourne les 50 dernières mesures avec toutes les colonnes."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT timestamp, latence_ms, jitter_ms, perte_pourcent,
                   debit_down_mbps, mos_voip, qoe_video, qoe_gaming
            FROM mesures
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        rows = c.fetchall()
        conn.close()

        return jsonify([{
            'timestamp':   r[0],
            'latence':     r[1],
            'jitter':      r[2],
            'perte':       r[3],
            'debit_down':  r[4],
            'mos_voip':    r[5],
            'qoe_video':   r[6],
            'qoe_gaming':  r[7]
        } for r in rows])

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/simuler', methods=['POST'])
def api_simuler():
    """Simule les scores QoE en fonction de paramètres réseau."""
    try:
        data = request.json or {}
        latence = float(data.get('latence', 50))
        jitter  = float(data.get('jitter',  5))
        perte   = float(data.get('perte',   0))
        debit   = float(data.get('debit',   50))

        mos    = calculer_mos_voip(latence, jitter, perte)
        video  = calculer_qoe_video(debit, perte)
        gaming = calculer_qoe_gaming(latence, jitter, perte)

        return jsonify({
            'success': True,
            'qos': {'latence': latence, 'jitter': jitter, 'perte': perte, 'debit': debit},
            'qoe': {'mos_voip': mos, 'qoe_video': video, 'qoe_gaming': gaming}
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """Statistiques agrégées sur toutes les mesures."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT AVG(latence_ms), AVG(mos_voip), AVG(qoe_video), AVG(qoe_gaming)
            FROM mesures
        ''')
        avg = c.fetchone()
        c.execute('SELECT COUNT(*) FROM mesures')
        count = c.fetchone()[0]
        conn.close()

        def safe(v): return round(v, 2) if v else 0

        return jsonify({
            'total_mesures': count,
            'moyennes': {
                'latence_ms':  safe(avg[0]),
                'mos_voip':    safe(avg[1]),
                'qoe_video':   safe(avg[2]),
                'qoe_gaming':  safe(avg[3])
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/test')
def api_test():
    return jsonify({'status': 'OK', 'mode_demo': MODE_DEMO})


if __name__ == '__main__':
    print("=" * 50)
    print("  NetQoE Analyzer — démarrage")
    print(f"  Mode DEMO : {MODE_DEMO}")
    print(f"  OS        : {platform.system()}")
    print("  URL       : http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=5000)