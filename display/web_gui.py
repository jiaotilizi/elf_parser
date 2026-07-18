from .base import DisplayBase, ResourceMetadata
from typing import Dict, List, Any
import threading
import time


class WebGuiDisplay(DisplayBase):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)
        self.server_thread = None
        self.running = False
        self.port = self.options.get('port', 5000)
    
    def show_resource(self, resource_type: str, data: List[Dict], metadata: ResourceMetadata):
        print(f"[WebGUI] {metadata.icon} {metadata.label}: {len(data)} items")
    
    def show_detail(self, resource_type: str, address: int):
        print(f"[WebGUI] Detail: {resource_type} @ 0x{address:08X}")
    
    def _start_server(self):
        try:
            from flask import Flask, jsonify, render_template_string
            
            app = Flask(__name__)
            
            @app.route('/api/resources')
            def api_resources():
                if self.data_adapter:
                    resource_types = self.data_adapter.get_all_resource_types()
                    result = {}
                    for rt in resource_types:
                        result[rt] = self.data_adapter.get_resource_data(rt)
                    return jsonify(result)
                return jsonify({})
            
            @app.route('/api/metadata/<resource_type>')
            def api_metadata(resource_type):
                if self.data_adapter:
                    meta = self.data_adapter.get_resource_metadata(resource_type)
                    if meta:
                        return jsonify({
                            'resource_type': meta.resource_type,
                            'label': meta.label,
                            'icon': meta.icon,
                            'fields': meta.fields,
                        })
                return jsonify({})
            
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
                            h2 { display: flex; align-items: center; gap: 10px; }
                        </style>
                    </head>
                    <body>
                        <h1>ELF Parser - Web GUI</h1>
                        <div id="content">Loading data...</div>
                        <script>
                            async function loadData() {
                                const resources = await fetch('/api/resources').then(r => r.json());
                                let html = '';
                                for(let key in resources) {
                                    const meta = await fetch(`/api/metadata/${key}`).then(r => r.json());
                                    const icon = meta.icon || '📦';
                                    const label = meta.label || key;
                                    html += `<div class="panel"><h2>${icon} ${label}</h2>`;
                                    if(resources[key].length > 0) {
                                        html += '<table><thead><tr>';
                                        const headers = meta.fields ? meta.fields.map(f => f.label) : Object.keys(resources[key][0]);
                                        headers.forEach(h => html += `<th>${h}</th>`);
                                        html += '</tr></thead><tbody>';
                                        resources[key].forEach(item => {
                                            html += '<tr>';
                                            headers.forEach(h => {
                                                const fieldName = meta.fields ? meta.fields.find(f => f.label === h)?.name : h;
                                                let value = item[fieldName];
                                                if(typeof value === 'number' && value >= 0) {
                                                    value = '0x' + value.toString(16).toUpperCase().padStart(8, '0');
                                                }
                                                html += `<td>${value}</td>`;
                                            });
                                            html += '</tr>';
                                        });
                                        html += '</tbody></table>';
                                    } else {
                                        html += '<p>(Empty)</p>';
                                    }
                                    html += '</div>';
                                }
                                document.getElementById('content').innerHTML = html;
                            }
                            loadData();
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
        print(f"[WebGUI] Open http://localhost:{self.port} in your browser")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[WebGUI] Stopping server...")
            self.running = False