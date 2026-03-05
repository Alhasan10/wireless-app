from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import math
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

def erlang_b(E, m):
    """Calculate blocking probability using Erlang B formula."""
    InvB = 1.0
    for j in range(1, m + 1):
        InvB = 1.0 + InvB * (j / E)
    return 1.0 / InvB

def find_max_E_given_gos(channels, gos, step=0.01, max_E=1000):
    """Find max traffic E such that ErlangB(E, channels) ≤ GOS"""
    E = 0.01
    while E <= max_E:
        if erlang_b(E, channels) > gos:
            return round(E - step, 4)
        E += step
    return None


# Safe debug print that handles None values
if OPENROUTER_API_KEY:
    print(f"DEBUG: AIML API Key loaded: {OPENROUTER_API_KEY[:5]}...{OPENROUTER_API_KEY[-5:]}")
else:
    print("WARNING: OPENROUTER_API_KEY environment variable is not set!")


def get_ai_explanation(scenario, inputs, results):
    """Get AI explanation for calculations using AIML API"""

    if not OPENROUTER_API_KEY:
        return "AI explanation not available: AIML API key is not configured."

    def safe_fmt(value, digits=2):
        try:
            return f"{float(value):.{digits}f}"
        except (ValueError, TypeError):
            return "N/A"

    try:
        if scenario == "link_budget":
            prompt = f"""
Explain this link budget calculation:

Inputs:
- Frequency: {inputs.get("frequency", "N/A")} Hz
- Distance: {inputs.get("distance", "N/A")} meters
- TX Gain: {inputs.get("tx_gain", "N/A")} dBi
- RX Gain: {inputs.get("rx_gain", "N/A")} dBi
- RX Amp Gain: {inputs.get("rx_amp_gain", "N/A")} dB
- Feed Line Loss: {inputs.get("feed_line_loss", "N/A")} dB
- Other Losses: {inputs.get("other_losses", "N/A")} dB
- Fade Margin: {inputs.get("fade_margin", "N/A")} dB
- Eb/N0: {inputs.get("eb_n0", "N/A")} dB
- Noise Figure: {inputs.get("noise_figure", "N/A")} dB
- Bandwidth: {inputs.get("bandwidth_hz", "N/A")} Hz
- Desired Link Margin: {inputs.get("desired_margin", "N/A")} dB

Results:
- Path Loss (Lp): {safe_fmt(results.get("path_loss"))} dB
- Required Received Power (Pr): {safe_fmt(results.get("required_received_power"))} dBm
- Required Transmit Power (Pt): {safe_fmt(results.get("required_transmit_power"))} dBm

Explain how the above factors influence power requirements using:
Lp = 20·log₁₀(f) + 20·log₁₀(d) - 147.56
            """

        elif scenario == "wireless_system":
            prompt = f"""
Explain this wireless system rate calculation:

Inputs:
- Sampling Rate: {inputs.get("sampling_rate", "N/A")} Hz
- Quantization Bits: {inputs.get("quantization_bits", "N/A")} bits
- Source Coding Rate: {inputs.get("source_coding_rate", "N/A")}
- Channel Coding Rate: {inputs.get("channel_coding_rate", "N/A")}
- Overhead: {inputs.get("overhead_percentage", "N/A")}% extra

Results:
- Quantization Rate: {safe_fmt(results.get("quantization_rate"))} bps
- Source Encoder Rate: {safe_fmt(results.get("source_encoder_rate"))} bps
- Channel Encoder Rate: {safe_fmt(results.get("channel_encoder_rate"))} bps
- Interleaver Rate: {safe_fmt(results.get("interleaver_rate"))} bps
- Overhead Rate: {safe_fmt(results.get("overhead_rate"))} bps
- Burst Format Rate: {safe_fmt(results.get("burst_format_rate"))} bps

Explain the signal processing flow and why data rate increases across stages.
            """

        elif scenario == "ofdm":
            prompt = f"""
Explain this OFDM system calculation:

Inputs:
- Channel Bandwidth: {inputs.get("channel_bandwidth")} Hz
- RB Bandwidth: {inputs.get("rb_bandwidth")} Hz
- Subcarrier Spacing: {inputs.get("subcarrier_spacing")} Hz
- Guard Time: {inputs.get("guard_time")} s
- Modulation Order: {inputs.get("modulation_order")}-QAM
- Coding Rate: {inputs.get("coding_rate")}
- Num OFDM Symbols: {inputs.get("num_symbols")}

Results:
- Num RB: {results.get("num_rb")}
- Subcarriers per RB: {results.get("subcarriers_per_rb")}
- REs per RB: {results.get("re_per_rb")}
- Total REs: {results.get("total_res_elements")}
- Symbol Duration: {safe_fmt(results.get("symbol_duration_ms"))} ms
- Bits per RE: {safe_fmt(results.get("bits_per_re"))}
- Data Rate per RE: {safe_fmt(results.get("re_data_rate"))} bps
- OFDM Symbol Data Rate: {safe_fmt(results.get("ofdm_symbol_data_rate") / 1e6)} Mbps
- Total Capacity: {safe_fmt(results.get("total_capacity"))} Mbps
- Spectral Efficiency: {safe_fmt(results.get("spectral_efficiency"))} bps/Hz

Describe how parallel transmission and modulation parameters affect capacity and efficiency.
            """

        elif scenario == "cellular":
            prompt = f"""
Explain this cellular capacity calculation:

Inputs:
- Area: {inputs.get("area", "N/A")} km²
- Cell Radius: {inputs.get("radius", "N/A")} km
- Frequency Reuse Factor: {inputs.get("reuse", "N/A")}
- Total Spectrum: {inputs.get("spectrum", "N/A")} MHz
- Channel Bandwidth: {inputs.get("channel_bw", "N/A")} kHz
- Grade of Service (GOS): {safe_fmt(float(inputs.get("gos", 0)) * 100)}%
- Traffic/User: {inputs.get("traffic_per_user", "N/A")} Erlangs

Results:
- Cell Area: {safe_fmt(results.get("cell_area"))} km²
- Number of Cells: {results.get("num_cells")}
- Channels/Cell: {results.get("channels_per_cell")}
- Traffic/Cell: {safe_fmt(results.get("traffic_per_cell"))} Erlangs
- Users/Cell: {results.get("max_supported_users_per_cell")}
- Total Users: {results.get("max_supported_users")}
- Mobiles per Channel: {safe_fmt(results.get("mobiles_per_channel"))}
- Max Concurrent Users: {results.get("max_concurrent_users")}
- Max Carried Traffic: {safe_fmt(results.get("max_carried_traffic"))} Erlangs

Explain how channel reuse, Erlang B, and user traffic affect capacity and blocking probability.
            """

        else:
            prompt = "Explain this wireless communication engineering calculation."

        # API call to OpenRouter
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "mistralai/mistral-7b-instruct:free",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a wireless communication engineering expert. Provide clear, technical explanations that are accessible to engineering students and professionals."
                },
                {
                    "role": "user",
                    "content": prompt.strip()
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            return response_json["choices"][0]["message"]["content"]
        else:
            return "AI explanation temporarily unavailable. No response choices found."

    except requests.exceptions.RequestException as req_err:
        return f"AI explanation not available due to network error: {str(req_err)}"
    except Exception as e:
        return f"AI explanation not available: {str(e)}"

@app.route('/')
def home():
    return render_template('Home.html')

@app.route('/wirelessTool')
def index():
    return render_template('index.html')


@app.route('/api/link-budget', methods=['POST'])
def calculate_link_budget():
    try:
        data = request.json

        # Inputs (in dB/dBm unless noted)
        tx_gain = float(data.get('tx_gain', 0))
        rx_gain = float(data.get('rx_gain', 0))
        rx_amp_gain = float(data.get('rx_amp_gain', 0))
        feed_line_loss = float(data.get('feed_line_loss', 0))
        other_losses = float(data.get('other_losses', 0))
        fade_margin = float(data.get('fade_margin', 0))
        eb_n0 = float(data.get('eb_n0', 0))
        noise_fig = float(data.get('noise_figure', 0))
        bandwidth_hz = float(data.get('bandwidth_hz', 1))
        margin_db = float(data.get('desired_margin', 10))

        frequency = float(data.get('frequency', 0))  # Hz
        distance = float(data.get('distance', 0))    # m

        if frequency <= 0 or distance <= 0:
            return jsonify({'error': 'Frequency and distance must be > 0'}), 400

        # Constants
        k_db = -228.6
        T_db = 10 * math.log10(290)
        R_db = 10 * math.log10(bandwidth_hz)

        # FSPL in dB for f in Hz and d in meters
        Lp = 20 * math.log10(frequency) + 20 * math.log10(distance) - 147.56

        # Calculate required received power
        Pr = margin_db + k_db + T_db + noise_fig + R_db + eb_n0

        # Calculate required transmitted power
        Pt = margin_db + k_db + T_db + noise_fig + R_db + eb_n0 + Lp + feed_line_loss + other_losses + fade_margin - tx_gain - rx_gain - rx_amp_gain

        results = {
            "path_loss": round(Lp, 2),
            "required_received_power": round(Pr, 2),
            "required_transmit_power": round(Pt, 2),
            "formulas": {
                "received_power_equation": "M = Pr - k - T - NF - R - (Eb/N0)",
                "transmit_power_equation": "M = Pt + Gt + Gr + Ar - k - T - NF - R - (Eb/N0) - Lp - Lf - Lo - Fmargin",
                "fspl": "Lp = 20log₁₀(f) + 20log₁₀(d) - 147.56  (f in Hz, d in meters)"
            }
        }

        ai_explanation = get_ai_explanation('link_budget', data, results)
        results["ai_explanation"] = ai_explanation

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/wireless-system', methods=['POST'])
def calculate_wireless_system():
    try:
        data = request.json

        # Get inputs
        sampling_rate = float(data.get('sampling_rate', 0))  # Hz
        quantization_bits = int(data.get('quantization_bits', 8))
        source_coding_rate = float(data.get('source_coding_rate', 0.5))
        channel_coding_rate = float(data.get('channel_coding_rate', 0.75))
        overhead_percentage = float(data.get('overhead_percentage', 20))  # Overhead percentage

        # Calculate rates at each stage
        quantization_rate = sampling_rate * quantization_bits
        source_encoder_rate = quantization_rate * source_coding_rate
        channel_encoder_rate = source_encoder_rate / channel_coding_rate
        interleaver_rate = channel_encoder_rate  # No rate change

        # Calculate overhead rate: rate + (overhead_percentage/100) * rate
        overhead_rate = interleaver_rate * (1 + overhead_percentage / 100)

        # Burst format rate is same as overhead rate
        burst_format_rate = overhead_rate

        results = {
            'sampling_rate': sampling_rate,
            'quantization_rate': quantization_rate,
            'source_encoder_rate': source_encoder_rate,
            'channel_encoder_rate': channel_encoder_rate,
            'interleaver_rate': interleaver_rate,
            'overhead_rate': overhead_rate,
            'burst_format_rate': burst_format_rate,
            'overhead_percentage': overhead_percentage,
            'formulas': {
                'quantization': 'Rate = Sampling_Rate × Bits_per_Sample',
                'source_coding': 'Rate = Input_Rate × Coding_Rate',
                'channel_coding': 'Rate = Input_Rate / Coding_Rate',
                'overhead': 'Rate = Input_Rate × (1 + Overhead_Percentage/100)',
                'burst_format': 'Rate = Overhead_Rate (same as overhead rate)'
            }
        }

        # Get AI explanation
        ai_explanation = get_ai_explanation('wireless_system', data, results)
        results['ai_explanation'] = ai_explanation

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/ofdm', methods=['POST'])
def calculate_ofdm():
    """General-purpose OFDM calculator (no hard-coded standards)"""
    try:
        data = request.json

        bw = float(data.get('channel_bandwidth'))  # 1) Channel BW (Hz)
        rb_bw = float(data.get('rb_bandwidth'))  # 2) RB BW (Hz)
        subcarrier_spacing = float(data.get('subcarrier_spacing'))  # 4) Δf (Hz)
        guard_time = float(data.get('guard_time'))  # 7) Guard time (s)
        modulation_order = int(data.get('modulation_order'))  # 9) M-QAM
        coding_rate = float(data.get('coding_rate'))  # 8) Coding rate
        num_symbols = int(data.get('num_symbols'))  # 6) Symbols

        # Derived calculations
        num_rb = int(bw // rb_bw)  # 3) Num RB
        sc_per_rb = int(rb_bw // subcarrier_spacing)  # 5) Subcarriers per RB
        re_per_rb = sc_per_rb * num_symbols  # REs per RB
        total_res_elements = re_per_rb * num_rb  # All REs

        symbol_duration = guard_time + 1.0 / subcarrier_spacing  # seconds
        bits_per_symbol = math.log2(modulation_order)
        bits_per_re = bits_per_symbol * coding_rate

        # Data rate calculations
        re_data_rate = bits_per_re / symbol_duration  # bps per RE

        # NEW: OFDM Symbol data rate
        bits_per_ofdm_symbol = sc_per_rb * num_rb * bits_per_re  # Total bits in one OFDM symbol
        ofdm_symbol_data_rate = bits_per_ofdm_symbol / symbol_duration  # bps per OFDM symbol

        # NEW: Resource Block data rate
        rb_data_rate = re_data_rate * re_per_rb  # bps per RB
        rb_data_rate_mbps = rb_data_rate / 1e6  # Mbps per RB

        # Total capacity and spectral efficiency
        total_capacity_bps = total_res_elements * bits_per_re / symbol_duration
        total_capacity_mbps = total_capacity_bps / 1e6
        spectral_efficiency = total_capacity_bps / bw

        results = {
            'num_rb': num_rb,
            'subcarriers_per_rb': sc_per_rb,
            're_per_rb': re_per_rb,
            'total_res_elements': total_res_elements,
            'symbol_duration': round(symbol_duration, 8),
            'symbol_duration_ms': round(symbol_duration * 1000, 4),
            'guard_time': guard_time,
            'guard_time_ms': round(guard_time * 1000, 4),
            'bits_per_re': bits_per_re,
            're_data_rate': re_data_rate,
            'ofdm_symbol_data_rate': ofdm_symbol_data_rate,  # NEW
            'rb_data_rate': rb_data_rate,  # NEW
            'rb_data_rate_mbps': rb_data_rate_mbps,  # NEW
            'total_capacity': total_capacity_mbps,
            'spectral_efficiency': spectral_efficiency,
            'formulas': {
                'num_rb': 'Num_RB = BW / RB_BW',
                'subcarriers_per_rb': 'SC_per_RB = RB_BW / Δf',
                're_per_rb': 'RE_per_RB = SC_per_RB × Num_Symbols',
                'symbol_duration': 'T_sym = Guard_time + 1 / Δf',
                'bits_per_re': 'Bits_RE = log₂(M) × Coding_rate',
                're_data_rate': 'Rate_RE = Bits_RE / T_sym',
                'ofdm_symbol_data_rate': 'Rate_Symbol = (SC_per_RB × Num_RB × Bits_RE) / T_sym',  # NEW
                'rb_data_rate': 'Rate_RB = Rate_RE × RE_per_RB',  # NEW
                'total_capacity': 'Capacity = Rate_RE × Total_REs',
                'spectral_efficiency': 'SE = Capacity / BW'
            }
        }

        # Get AI explanation (ADD THIS LINE)
        ai_explanation = get_ai_explanation('ofdm', data, results)
        results['ai_explanation'] = ai_explanation

        print(f"Symbol duration: {symbol_duration}")
        print(f"OFDM Symbol data rate: {ofdm_symbol_data_rate} bps")
        print(f"RB data rate: {rb_data_rate} bps ({rb_data_rate_mbps} Mbps)")

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/cellular-design', methods=['POST'])
def calculate_cellular_design():
    try:
        data = request.json

        # Get inputs
        coverage_area = float(data.get('coverage_area', 100))  # km²
        users_per_km2 = float(data.get('users_per_km2', 1000))
        traffic_per_user = float(data.get('traffic_per_user', 0.025))  # Erlang
        blocking_probability = float(data.get('blocking_probability', 0.02))
        frequency_reuse = int(data.get('frequency_reuse', 7))
        cell_radius = float(data.get('cell_radius', 2))  # km

        # Calculate cell area
        cell_area = 2.6 * (cell_radius ** 2)  # Hexagonal cell area

        # Calculate number of cells needed
        num_cells = math.ceil(coverage_area / cell_area)

        # Calculate traffic and channels
        total_users = coverage_area * users_per_km2
        users_per_cell = total_users / num_cells
        traffic_per_cell = users_per_cell * traffic_per_user

        # Erlang B calculation (approximation)
        channels_per_cell = math.ceil(traffic_per_cell + 3 * math.sqrt(traffic_per_cell))

        # System capacity
        total_channels = channels_per_cell * num_cells
        system_capacity = total_users

        results = {
            'num_cells': num_cells,
            'cell_area': cell_area,
            'users_per_cell': users_per_cell,
            'traffic_per_cell': traffic_per_cell,
            'channels_per_cell': channels_per_cell,
            'total_channels': total_channels,
            'system_capacity': system_capacity,
            'frequency_reuse_factor': frequency_reuse,
            'formulas': {
                'cell_area': 'A = 2.6 × R²',
                'traffic': 'A = λ × h (users × holding_time)',
                'channels': 'C ≈ A + 3√A (Erlang B approximation)'
            }
        }

        # Get AI explanation
        ai_explanation = get_ai_explanation('cellular', data, results)
        results['ai_explanation'] = ai_explanation

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/cellular-capacity', methods=['POST'])
def cellular_capacity():
    try:
        data = request.json

        area_km2 = float(data.get("area"))
        radius_km = float(data.get("radius"))
        reuse = int(data.get("reuse"))
        spectrum_mhz = float(data.get("spectrum"))
        channel_bw_khz = float(data.get("channel_bw"))
        gos = float(data.get("gos")) / 100.0
        traffic_per_user = float(data.get("traffic_per_user"))

        cell_area_km2 = 2.6 * (radius_km ** 2)
        num_cells = math.ceil(area_km2 / cell_area_km2)
        total_channels = (spectrum_mhz * 1000) / channel_bw_khz
        channels_per_cell = int(total_channels / reuse)

        E_per_cell = find_max_E_given_gos(channels_per_cell, gos)
        users_per_cell = E_per_cell / traffic_per_user
        total_users = users_per_cell * num_cells
        mobiles_per_channel = users_per_cell / channels_per_cell

        results = {
            'cell_area': round(cell_area_km2, 2),
            'num_cells': num_cells,
            'channels_per_cell': channels_per_cell,
            'traffic_per_cell': round(E_per_cell, 2),
            'max_supported_users_per_cell': int(users_per_cell),
            'max_supported_users': int(total_users),
            'mobiles_per_channel': round(mobiles_per_channel, 2),
            'max_concurrent_users': int(total_channels),
            'max_carried_traffic': round(E_per_cell * num_cells, 2),
            'formulas': {
                'cell_area': 'A_cell = 2.6 × R²',
                'number_of_cells': 'N_cells = Area / A_cell',
                'total_channels': 'Total Channels = (Spectrum × 1000) / Channel_BW',
                'channels_per_cell': 'Channels per Cell = Total Channels / Reuse Factor',
                'erlang_b': 'Find E such that B(E, C) ≤ GOS',
                'max_traffic': 'Max Traffic = E × N_cells',
                'users_per_cell': 'Users per Cell = Traffic per Cell / Traffic per User',
                'total_users': 'Total Users = Users per Cell × Number of Cells',
                'mobiles_per_channel': 'Mobiles per Channel = Users per Cell / Channels per Cell'
            }
        }

        # AI explanation (same style as /api/ofdm)
        ai_explanation = get_ai_explanation('cellular', data, results)
        results['ai_explanation'] = ai_explanation

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(
        debug=False,  # should be False in production
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))  # Render sets PORT automatically
    )