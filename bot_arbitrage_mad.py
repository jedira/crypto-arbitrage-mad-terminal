import time
import logging
from datetime import datetime
import threading
import ccxt
import gradio as gr
import plotly.graph_objects as go

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

class MoroccanArbitrageEngine:
    def __init__(self):
        self.is_running = False
        self.pair = 'BTC/USDT'
        self.refresh_rate = 2.0  # Vitesse par défaut en secondes
        self.usd_to_mad = 9.8438  # Taux fixe de référence (Bank Al-Maghrib)
        self.logs_list = []
        self.spread_history = []
        self.time_history = []
        self.lock = threading.Lock()
        
        # Connexions aux API mondiales
        self.binance = ccxt.binance({'enableRateLimit': True})
        self.kraken = ccxt.kraken({'enableRateLimit': True})

    def start_bot(self, pair_selection, speed):
        with self.lock:
            if self.is_running:
                return "Le robot tourne déjà."
            self.pair = pair_selection
            self.refresh_rate = float(speed)
            self.is_running = True
            self.logs_list = []
            self.spread_history = []
            self.time_history = []
            
        self.thread = threading.Thread(target=self._market_loop, daemon=True)
        self.thread.start()
        return f"Moteur LIVE démarré ({self.pair}) - Analyse toutes les {self.refresh_rate}s."

    def update_speed(self, speed):
        with self.lock:
            self.refresh_rate = float(speed)
        return f"Vitesse ajustée à {speed}s."

    def stop_bot(self):
        with self.lock:
            self.is_running = False
        return "Robot arrêté."

    def _market_loop(self):
        while True:
            with self.lock:
                if not self.is_running:
                    break
                current_speed = self.refresh_rate
            
            try:
                # Fetch tickers de prix mondiaux en USD
                b_ticker = self.binance.fetch_ticker(self.pair)
                k_ticker = self.kraken.fetch_ticker(self.pair)
                
                p_binance_usd = b_ticker['last']
                p_kraken_usd = k_ticker['last']
                
                if p_binance_usd and p_kraken_usd:
                    # Conversion Option 3 : USD vers MAD
                    p_binance_mad = p_binance_usd * self.usd_to_mad
                    p_kraken_mad = p_kraken_usd * self.usd_to_mad
                    
                    spread = ((p_kraken_usd - p_binance_usd) / p_binance_usd) * 100
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    with self.lock:
                        self.time_history.append(timestamp)
                        self.spread_history.append(spread)
                        
                        if len(self.spread_history) > 30:
                            self.time_history.pop(0)
                            self.spread_history.pop(0)
                            
                        log_msg = f"[{timestamp}] {self.pair} | Binance: {p_binance_mad:.2f} MAD | Kraken: {p_kraken_mad:.2f} MAD | Écart: {spread:.4f}%"
                        self.logs_list.append(log_msg)
                        if len(self.logs_list) > 15:
                            self.logs_list.pop(0)
            except Exception as e:
                logging.error(f"Erreur d'acquisition : {e}")
                
            time.sleep(current_speed)

    def get_ui_updates(self):
        with self.lock:
            status = f"🟢 SYNC REEL ({self.refresh_rate}s)" if self.is_running else "🔴 ARRÊTÉ"
            current_logs = "\n".join(self.logs_list[::-1])
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=self.time_history, y=self.spread_history,
                mode='lines+markers', name='Spread (%)',
                line=dict(color='#009688', width=2)
            ))
            fig.update_layout(
                title=f"Écart inter-plateformes en direct — {self.pair}",
                template="plotly_dark", xaxis_title="Temps", yaxis_title="Écart (%)",
                margin=dict(l=20, r=20, t=40, b=20), height=280
            )
            
            last_spread = f"{self.spread_history[-1]:.3f}%" if self.spread_history else "0.00%"
            return status, last_spread, current_logs, fig

engine = MoroccanArbitrageEngine()

with gr.Blocks(theme=gr.themes.Soft(), title="Maroc Crypto Terminal") as demo:
    gr.Markdown("# 🇲🇦 Terminal d'Arbitrage Convertisseur Dirham (MAD)")
    
    with gr.Row():
        with gr.Column(scale=1):
            pair_dd = gr.Dropdown(choices=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'], value='BTC/USDT', label="Actif")
            
            # Curseur ajustable pour gérer la connexion réseau
            speed_slider = gr.Slider(minimum=1.0, maximum=10.0, value=3.0, step=0.5, label="Pause entre requêtes (sec)")
            
            start_btn = gr.Button("LANCER LE FLUX MAD", variant="primary")
            stop_btn = gr.Button("COUPER", variant="stop")
            status_txt = gr.Textbox(label="Statut", value="🔴 ARRÊTÉ", interactive=False)
            spread_lbl = gr.Label(label="Dernier Spread Brut")
            
        with gr.Column(scale=2):
            plot_output = gr.Plot(label="Graphique Spread")
            
    logs_txt = gr.TextArea(label="Prix convertis en Dirhams (MAD) en direct", lines=8, interactive=False)

    start_btn.click(fn=engine.start_bot, inputs=[pair_dd, speed_slider], outputs=status_txt)
    speed_slider.change(fn=engine.update_speed, inputs=speed_slider, outputs=status_txt)
    stop_btn.click(fn=engine.stop_bot, outputs=status_txt)
    
    auto_refresh = gr.Timer(value=1.5)
    auto_refresh.tick(fn=engine.get_ui_updates, outputs=[status_txt, spread_lbl, logs_txt, plot_output])

if __name__ == "__main__":
        demo.launch(server_port=7862, share=True)

