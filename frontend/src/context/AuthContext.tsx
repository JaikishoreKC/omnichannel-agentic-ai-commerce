import React, { createContext, useContext, useState, useEffect } from "react";
import { login as apiLogin, register as apiRegister, setToken, setSessionId } from "../api";
import type { AuthUser } from "../types";

interface AuthContextType {
    user: AuthUser | null;
    isAuthenticated: boolean;
    login: (email: string, pass: string) => Promise<void>;
    register: (name: string, email: string, pass: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<AuthUser | null>(() => {
        const saved = localStorage.getItem("commerce_user");
        return saved ? JSON.parse(saved) : null;
    });

    const isAuthenticated = !!user;

    const login = async (email: string, pass: string) => {
        const res = await apiLogin({ email, password: pass });
        setUser(res.user);
        setToken(res.accessToken);
        if (res.sessionId) setSessionId(res.sessionId);
        localStorage.setItem("commerce_user", JSON.stringify(res.user));
    };

    const register = async (name: string, email: string, pass: string) => {
        const res = await apiRegister({ name, email, password: pass });
        setUser(res.user);
        setToken(res.accessToken);
        if (res.sessionId) setSessionId(res.sessionId);
        localStorage.setItem("commerce_user", JSON.stringify(res.user));
    };

    const logout = () => {
        setUser(null);
        setToken(null);
        localStorage.removeItem("commerce_user");
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
