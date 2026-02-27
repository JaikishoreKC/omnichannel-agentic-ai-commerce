import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Star, ShoppingCart, ArrowLeft, ShieldCheck, Truck, RotateCcw } from "lucide-react";
import { fetchProduct } from "../api";
import type { Product, ProductVariant } from "../types";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { cn } from "../utils/cn";
import { useCart } from "../context/CartContext";

const ProductDetailPage: React.FC = () => {
    const { productId } = useParams<{ productId: string }>();
    const navigate = useNavigate();
    const { addItem } = useCart();
    const [product, setProduct] = useState<Product | null>(null);
    const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isAdding, setIsAdding] = useState(false);
    const [activeImage, setActiveImage] = useState(0);

    useEffect(() => {
        const load = async () => {
            if (!productId) return;
            try {
                setIsLoading(true);
                const data = await fetchProduct(productId);
                setProduct(data);
                const initialVariant = data.variants.find(v => v.inStock) || data.variants[0];
                setSelectedVariant(initialVariant);
            } finally {
                setIsLoading(false);
            }
        };
        load();
    }, [productId]);

    const handleAddToCart = async () => {
        if (!product || !selectedVariant) return;
        setIsAdding(true);
        try {
            await addItem(product.id, selectedVariant.id, 1);
        } finally {
            setIsAdding(false);
        }
    };

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                <Skeleton className="aspect-square rounded-3xl" />
                <div className="space-y-6">
                    <Skeleton className="h-10 w-3/4" />
                    <Skeleton className="h-6 w-1/4" />
                    <Skeleton className="h-32 w-full" />
                    <div className="flex gap-4">
                        <Skeleton className="h-14 flex-1 rounded-2xl" />
                        <Skeleton className="h-14 w-14 rounded-2xl" />
                    </div>
                </div>
            </div>
        );
    }

    if (!product) return <div className="text-center py-24">Product not found</div>;

    return (
        <div className="space-y-12 animate-fade-in">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-brand transition-colors"
            >
                <ArrowLeft size={16} /> Back
            </button>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
                {/* Images */}
                <div className="space-y-4">
                    <div className="aspect-square rounded-[40px] bg-surface-100 overflow-hidden border border-line flex items-center justify-center p-12">
                        <img
                            src={product.images[activeImage]}
                            alt={product.name}
                            className="w-full h-full object-contain"
                        />
                    </div>
                    <div className="flex gap-4 overflow-x-auto pb-2">
                        {product.images.map((img, idx) => (
                            <button
                                key={idx}
                                onClick={() => setActiveImage(idx)}
                                className={cn(
                                    "w-24 h-24 rounded-2xl border-2 transition-all p-4 bg-surface-50 shrink-0",
                                    activeImage === idx ? "border-brand shadow-sm" : "border-transparent opacity-60 hover:opacity-100"
                                )}
                            >
                                <img src={img} alt={`${product.name} ${idx}`} className="w-full h-full object-contain" />
                            </button>
                        ))}
                    </div>
                </div>

                {/* Info */}
                <div className="space-y-8">
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Badge variant="secondary">{product.category}</Badge>
                            <Badge variant="outline">{product.brand}</Badge>
                        </div>
                        <h1 className="text-5xl font-bold leading-tight">{product.name}</h1>
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-1 text-amber-500">
                                <Star size={18} fill="currentColor" />
                                <span className="text-sm font-bold text-ink">{product.rating}</span>
                            </div>
                            <span className="text-sm text-slate-400 font-medium">({product.reviewCount} verified reviews)</span>
                        </div>
                    </div>

                    <div className="text-4xl font-display font-bold text-ink">
                        ${product.price.toFixed(2)}
                    </div>

                    <p className="text-lg text-slate-500 leading-relaxed">
                        {product.description}
                    </p>

                    {/* Variants */}
                    <div className="space-y-4">
                        <h4 className="font-bold">Select Style & Size</h4>
                        <div className="flex flex-wrap gap-3">
                            {product.variants.map((v) => (
                                <button
                                    key={v.id}
                                    onClick={() => setSelectedVariant(v)}
                                    disabled={!v.inStock}
                                    className={cn(
                                        "px-6 py-3 rounded-2xl border text-sm font-bold transition-all",
                                        selectedVariant?.id === v.id
                                            ? "border-brand bg-brand/5 text-brand shadow-sm"
                                            : "border-line text-slate-500 hover:border-brand/40",
                                        !v.inStock && "opacity-30 cursor-not-allowed grayscale"
                                    )}
                                >
                                    {v.color} - {v.size}
                                    {!v.inStock && " (Sold Out)"}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="flex gap-4 pt-4">
                        <Button
                            size="lg"
                            className="flex-1 rounded-2xl gap-3 shadow-lg h-16"
                            onClick={handleAddToCart}
                            isLoading={isAdding}
                        >
                            <ShoppingCart size={20} /> Add to Bag
                        </Button>
                    </div>

                    {/* Features */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-8 border-t border-line">
                        {[
                            { icon: ShieldCheck, label: "2 Year Warranty" },
                            { icon: Truck, label: "Express Shipping" },
                            { icon: RotateCcw, label: "30-Day Returns" }
                        ].map((f, i) => (
                            <div key={i} className="flex flex-col items-center text-center gap-2">
                                <div className="w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center text-slate-500">
                                    <f.icon size={20} />
                                </div>
                                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{f.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export { ProductDetailPage };
