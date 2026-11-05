// shared/static/js/websocket.js
class WebSocketClient {
    constructor(url) {
        this.url = url; this.ws = null; this.callbacks = [];
    }
    connect() {
        this.ws = new WebSocket(this.url);
        this.ws.onopen = () => { console.log("🔌 WebSocket متصل"); };
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.callbacks.forEach(cb => cb(data));
        };
        this.ws.onclose = () => { console.log("🔌 WebSocket مغلق"); };
        this.ws.onerror = (error) => { console.error("❌ WebSocket خطأ:", error); };
    }
    send(data) { if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(data)); }
    onMessage(callback) { this.callbacks.push(callback); }
    disconnect() { if (this.ws) this.ws.close(); }
}
