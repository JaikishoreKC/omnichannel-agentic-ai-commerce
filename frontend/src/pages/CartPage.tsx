import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShoppingBag, Trash2, Plus, Minus, ArrowRight, CreditCard, Truck, ShieldCheck } from "lucide-react";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { checkout } from "../api";
import { cn } from "../utils/cn";

const CartPage: React.FC = () => {
    const { cart, refreshCart, isLoading: isCartLoading } = useCart();
    const { isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [isCheckingOut, setIsCheckingOut] = useState(false);

    const handleCheckout = async () => {
        if (!isAuthenticated) {
            navigate("/login?redirect=/cart");
            return;
        }

        setIsCheckingOut(true);
        try {
            // Mock shipping/payment for now as per previous project vibes
            await checkout({
                shippingAddress: {
                    name: "E2E User",
                    line1: "123 Main St",
                    city: "New York",
                    state: "NY",
                    postalCode: "10001",
                    country: "US"
                },
                paymentMethod: {
                    type: "card",
                    token: "tok_visa"
                }
            });
            await refreshCart();
            alert("Order placed successfully!");
            navigate("/account");
        } catch (err) {
            alert("Checkout failed: " + (err instanceof Error ? err.message : "Unknown error"));
        } finally {
            setIsCheckingOut(false);
        }
    };

    if (isCartLoading && !cart) {
        return (
            <div className="py-24 text-center space-y-4">
                <div className="animate-spin inline-block w-8 h-8 border-4 border-brand border-t-transparent rounded-full" />
                <p className="text-slate-500 font-medium">Crunching your cart data...</p>
            </div>
        );
    }

    if (!cart || cart.items.length === 0) {
        return (
            <div className="py-24 flex flex-col items-center justify-center text-center space-y-6">
                <div className="w-24 h-24 rounded-[32px] bg-surface-100 flex items-center justify-center text-slate-300">
                    <ShoppingBag size={48} />
                </div>
                <div className="space-y-2">
                    <h1 className="text-3xl font-bold">Your bag is empty</h1>
                    <p className="text-slate-500 max-w-xs">Looks like you haven't added anything to your bag yet.</p>
                </div>
                <Link to="/products">
                    <Button size="lg" className="rounded-2xl px-8">
                        Start Shopping
                    </Button>
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-12 animate-fade-in">
            <h1 className="text-4xl font-bold">Shopping <span className="text-brand">Bag</span></h1>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 items-start">
                {/* Cart Items */}
                <div className="lg:col-span-2 space-y-6" data-testid="cart-list">
                    {cart.items.map((item) => (
                        <div key={item.itemId} className="premium-card flex flex-col sm:flex-row items-center gap-6 p-4">
                            <div className="w-24 h-24 rounded-2xl bg-surface-50 shrink-0 p-4 border border-line flex items-center justify-center">
                                <img src={item.image} alt={item.name} className="w-full h-full object-contain" />
                            </div>

                            <div className="flex-1 space-y-1 text-center sm:text-left">
                                <h4 className="font-bold text-lg">{item.name}</h4>
                                <p className="text-sm text-slate-500">Variant: {item.variantId.split("_").pop()}</p>
                                <div className="text-brand font-bold mt-2">${item.price.toFixed(2)}</div>
                            </div>

                            <div className="flex items-center gap-4 bg-surface-50 rounded-xl border border-line p-1">
                                <button className="p-2 hover:text-brand transition-colors"><Minus size={16} /></button>
                                <span className="w-8 text-center font-bold">{item.quantity}</span>
                                <button className="p-2 hover:text-brand transition-colors"><Plus size={16} /></button>
                            </div>

                            <button className="p-2 text-slate-300 hover:text-red-500 transition-colors">
                                <Trash2 size={20} />
                            </button>
                        </div>
                    ))}
                </div>

                {/* Summary */}
                <div className="space-y-6">
                    <div className="premium-card bg-ink text-white">
                        <h3 className="text-xl font-bold mb-6">Order Summary</h3>

                        <div className="space-y-4 text-sm opacity-80">
                            <div className="flex justify-between">
                                <span>Subtotal</span>
                                <span>${cart.subtotal.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Shipping</span>
                                <span>{cart.shipping === 0 ? "FREE" : `$${cart.shipping.toFixed(2)}`}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Tax</span>
                                <span>${cart.tax.toFixed(2)}</span>
                            </div>
                            {cart.discount > 0 && (
                                <div className="flex justify-between text-cedar">
                                    <span>Discount</span>
                                    <span>-${cart.discount.toFixed(2)}</span>
                                </div>
                            )}
                        </div>

                        <div className="h-px bg-white/10 my-6" />

                        <div className="flex justify-between text-xl font-bold mb-8">
                            <span>Total</span>
                            <span className="text-brand-light">${cart.total.toFixed(2)}</span>
                        </div>

                        <Button
                            className="w-full h-14 rounded-2xl bg-brand-light hover:bg-white hover:text-ink shadow-lg gap-2"
                            onClick={handleCheckout}
                            isLoading={isCheckingOut}
                            data-testid="checkout-button"
                        >
                            Checkout Now <ArrowRight size={20} />
                        </Button>

                        <div className="mt-6 space-y-4">
                            <div className="flex items-center gap-3 text-xs opacity-60">
                                <ShieldCheck size={14} /> Secure Checkout Guarantee
                            </div>
                            <div className="flex items-center gap-3 text-xs opacity-60">
                                <CreditCard size={14} /> All major cards accepted
                            </div>
                        </div>
                    </div>

                    <div className="premium-card bg-surface-50 border-dashed">
                        <h4 className="font-bold text-sm mb-4">Estimated Delivery</h4>
                        <div className="flex items-center gap-3 text-sm text-slate-500">
                            <Truck size={20} /> Arriving in 2-3 business days
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export { CartPage };
