import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles.css";
import App from "./App";
import { SessionProvider } from "./context/SessionContext";
import { AuthProvider } from "./context/AuthContext";
import { CartProvider } from "./context/CartContext";
import { ChatProvider } from "./context/ChatContext";
import { ThemeProvider } from "./context/ThemeContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <SessionProvider>
          <AuthProvider>
            <CartProvider>
              <ChatProvider>
                <App />
              </ChatProvider>
            </CartProvider>
          </AuthProvider>
        </SessionProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
