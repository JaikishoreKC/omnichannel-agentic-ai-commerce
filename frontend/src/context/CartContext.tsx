import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { fetchCart as apiFetchCart, addToCart as apiAddToCart } from "../api";
import { useSession } from "./SessionContext";
import { useAuth } from "./AuthContext";
import type { Cart, CartItem } from "../types";

interface CartContextType {
    cart: Cart | null;
    isLoading: boolean;
    addItem: (productId: string, variantId: string, quantity: number) => Promise<void>;
    refreshCart: () => Promise<void>;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { sessionId } = useSession();
    const { user } = useAuth();
    const [cart, setCart] = useState<Cart | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const refreshCart = useCallback(async () => {
        if (!sessionId) return;
        try {
            setIsLoading(true);
            const data = await apiFetchCart();
            setCart(data);
        } catch (err) {
            console.error("Failed to fetch cart", err);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        refreshCart();
    }, [sessionId, user, refreshCart]);

    const addItem = async (productId: string, variantId: string, quantity: number) => {
        await apiAddToCart({ productId, variantId, quantity });
        await refreshCart();
    };

    return (
        <CartContext.Provider value={{ cart, isLoading, addItem, refreshCart }}>
            {children}
        </CartContext.Provider>
    );
};

export const useCart = () => {
    const context = useContext(CartContext);
    if (context === undefined) {
        throw new Error("useCart must be used within a CartProvider");
    }
    return context;
};
