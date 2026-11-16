import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API_URL, getToken, refreshTokens } from "./api.js";
import { useAuth } from "./auth.jsx";
import Icon from "./components/Icon.jsx";

// API_URL is either absolute (http://localhost:8000, development) or a same-origin path
// (/api, behind nginx in production). WebSockets need an absolute ws:// or wss:// URL.
const WS_URL = API_URL.startsWith("/")
  ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${API_URL}/ws`
  : `${API_URL.replace(/^http/, "ws")}/ws`;
const LiveContext = createContext({ connected: false });

function showSystemNotification(event) {
  // Only when the tab is in the background: in front, the in-app toast is enough.
  if ("Notification" in window && Notification.permission === "granted" && document.hidden) {
    new Notification("RideMate", { body: event.message, icon: "/icon-192.png", tag: event.type });
  }
}

export function LiveProvider({ children }) {
  const { user } = useAuth();
  const [connected, setConnected] = useState(false);
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => setToasts((all) => all.filter((t) => t.id !== id)), []);

  useEffect(() => {
    if (!user) return undefined;
    let socket;
    let retryTimer;
    let attempt = 0;
    let stopped = false;

    function connect() {
      socket = new WebSocket(WS_URL);
      // The token goes in the first message, not the URL (URLs end up in server logs).
      socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token: getToken() }));
      socket.onmessage = (msg) => {
        const event = JSON.parse(msg.data);
        if (event.type === "ready") {
          attempt = 0;
          setConnected(true);
          return;
        }
        const id = `${Date.now()}-${Math.random()}`;
        setToasts((all) => [...all.slice(-2), { id, message: event.message }]);
        setTimeout(() => dismiss(id), 6000);
        showSystemNotification(event);
        // Pages listen for this to reload their data (see MyRides).
        window.dispatchEvent(new CustomEvent("ridemate:event", { detail: event }));
      };
      socket.onclose = async (closeEvent) => {
        setConnected(false);
        if (stopped) return;
        // 4401 = the server rejected our token (probably expired): refresh, then retry.
        if (closeEvent.code === 4401 && !(await refreshTokens())) {
          window.dispatchEvent(new Event("ridemate:logout"));
          return;
        }
        const delay = Math.min(30000, 1000 * 2 ** attempt); // back off: 1s, 2s, 4s ... 30s
        attempt += 1;
        retryTimer = setTimeout(connect, delay);
      };
    }

    connect();
    // Some proxies cut connections that stay silent; a tiny message keeps ours alive.
    const ping = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send("ping"), 25000);
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(ping);
      socket?.close();
    };
  }, [user, dismiss]);

  return (
    <LiveContext.Provider value={{ connected }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <button key={t.id} className="toast" onClick={() => dismiss(t.id)}>
            <span className="toast-icon">
              <Icon name="bell" size={18} />
            </span>
            <span>{t.message}</span>
          </button>
        ))}
      </div>
    </LiveContext.Provider>
  );
}

export const useLive = () => useContext(LiveContext);

// Run `callback` whenever a live event arrives (for pages that show affected data).
export function useLiveEvents(callback) {
  useEffect(() => {
    const handler = (e) => callback(e.detail);
    window.addEventListener("ridemate:event", handler);
    return () => window.removeEventListener("ridemate:event", handler);
  }, [callback]);
}

// Browsers only allow the permission prompt after a click, so it's a button, not automatic.
export function NotificationPrompt() {
  const supported = "Notification" in window;
  const [permission, setPermission] = useState(supported ? Notification.permission : "denied");
  if (permission !== "default") return null;
  return (
    <div className="card prompt">
      <span className="prompt-icon">
        <Icon name="bell" size={20} />
      </span>
      <span className="prompt-text">Get an alert when someone requests your ride, even in another tab.</span>
      <button className="small primary" onClick={() => Notification.requestPermission().then(setPermission)}>
        Turn on
      </button>
    </div>
  );
}
