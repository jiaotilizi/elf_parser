from .base import DisplayBase
from typing import Dict, List, Any
import threading
import time


class WebGuiDisplay(DisplayBase):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)
        self.server_thread = None
        self.running = False
        self.port = self.options.get('port', 5000)
    
    def show_rtos_tasks(self, tasks: List[Dict]):
        print(f"[WebGUI] Tasks: {len(tasks)} items")
    
    def show_rtos_mutexes(self, mutexes: List[Dict]):
        print(f"[WebGUI] Mutexes: {len(mutexes)} items")
    
    def show_rtos_semaphores(self, semaphores: List[Dict]):
        print(f"[WebGUI] Semaphores: {len(semaphores)} items")
    
    def show_rtos_queues(self, queues: List[Dict]):
        print(f"[WebGUI] Queues: {len(queues)} items")
    
    def show_rtos_events(self, events: List[Dict]):
        print(f"[WebGUI] Events: {len(events)} items")
    
    def show_rtos_timers(self, timers: List[Dict]):
        print(f"[WebGUI] Timers: {len(timers)} items")
    
    def show_rtos_block_pools(self, pools: List[Dict]):
        print(f"[WebGUI] Block Pools: {len(pools)} items")
    
    def show_rtos_byte_pools(self, pools: List[Dict]):
        print(f"[WebGUI] Byte Pools: {len(pools)} items")
    
    def show_test_points(self, test_points: List[Dict]):
        print(f"[WebGUI] Test Points: {len(test_points)} items")
    
    def show_detail(self, resource_type: str, address: int):
        print(f"[WebGUI] Detail: {resource_type} @ 0x{address:08X}")
    
    def _start_server(self):
        try:
            from flask import Flask, jsonify, render_template_string
            
            app = Flask(__name__)
            
            @app.route('/api/rtos_data')
            def api_rtos_data():
                if self.data_adapter:
                    return jsonify(self.data_adapter.get_rtos_data())
                return jsonify({})
            
            @app.route('/api/test_points')
            def api_test_points():
                if self.data_adapter:
                    return jsonify(self.data_adapter.get_test_points())
                return jsonify([])
            
            @app.route('/api/detail/<resource_type>/<int:address>')
            def api_detail(resource_type, address):
                if self.data_adapter:
                    return jsonify(self.data_adapter.get_detail(resource_type, address))
                return jsonify({})
            
            @app.route('/')
            def index():
                return render_template_string("""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>ELF Parser Web GUI</title>
                        <style>
                            body { font-family: monospace; margin: 20px; }
                            .panel { margin: 20px 0; padding: 20px; border: 1px solid #ccc; }
                            table { border-collapse: collapse; width: 100%; }
                            th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
                            th { background-color: #f2f2f2; }
                        </style>
                    </head>
                    <body>
                        <h1>ELF Parser - Web GUI</h1>
                        <div id="content">Loading data...</div>
                        <script>
                            fetch('/api/rtos_data').then(r => r.json()).then(data => {
                                let html = '';
                                for(let key in data) {
                                    html += `<div class="panel"><h2>${key}</h2>`;
                                    if(data[key].length > 0) {
                                        html += '<table><thead><tr>';
                                        const headers = Object.keys(data[key][0]);
                                        headers.forEach(h => html += `<th>${h}</th>`);
                                        html += '</tr></thead><tbody>';
                                        data[key].forEach(item => {
                                            html += '<tr>';
                                            headers.forEach(h => html += `<td>${item[h]}</td>`);
                                            html += '</tr>';
                                        });
                                        html += '</tbody></table>';
                                    }
                                    html += '</div>';
                                }
                                document.getElementById('content').innerHTML = html;
                            });
                        </script>
                    </body>
                    </html>
                """)
            
            print(f"[WebGUI] Starting server on http://localhost:{self.port}")
            app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
        except ImportError:
            print("[WebGUI] Flask not installed. Please install with: pip install flask")
        except Exception as e:
            print(f"[WebGUI] Server error: {e}")
    
    def run(self):
        if not self.data_adapter:
            print("Error: Data adapter not provided")
            return
        
        self.running = True
        self.server_thread = threading.Thread(target=self._start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        print("[WebGUI] Server started in background")
        print("[WebGUI] Open http://localhost:5000 in your browser")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[WebGUI] Stopping server...")
            self.running = False