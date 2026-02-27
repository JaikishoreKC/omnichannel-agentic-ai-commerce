import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShoppingBag, Sparkles, TrendingUp, Zap } from "lucide-react";
import { motion } from "framer-motion";
import { fetchProducts } from "../api";
import type { Product } from "../types";
import { ProductCard } from "../components/features/ProductCard";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { cn } from "../utils/cn";

const HomePage: React.FC = () => {
    const [products, setProducts] = useState<Product[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const data = await fetchProducts();
                setProducts(data.slice(0, 4));
            } finally {
                setIsLoading(false);
            }
        };
        load();
    }, []);

    return (
        <div className="space-y-24">
            {/* Hero Section */}
            <section className="relative h-[600px] overflow-hidden rounded-[40px] bg-ink flex items-center px-12">
                <div className="absolute inset-0 opacity-40">
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-brand/30 blur-[120px] rounded-full" />
                    <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-accent/20 blur-[100px] rounded-full" />
                </div>

                <div className="relative z-10 max-w-2xl space-y-8">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-white text-sm font-medium"
                    >
                        <Sparkles size={16} className="text-accent" />
                        <span>The Future of Shopping is Agentic</span>
                    </motion.div>

                    <motion.h1
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="text-6xl md:text-7xl font-display font-bold text-white leading-[1.1]"
                    >
                        Premium Gear<br />For <span className="text-brand-light">Everyone.</span>
                    </motion.h1>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="text-lg text-slate-300 max-w-lg"
                    >
                        Experience the next generation of omnichannel commerce.
                        Smart recommendations, AI-driven search, and seamless checkout.
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="flex items-center gap-4"
                    >
                        <Link to="/products">
                            <Button size="lg" className="rounded-2xl px-10 gap-2">
                                Shop Collection <ArrowRight size={20} />
                            </Button>
                        </Link>
                        <Link to="/about">
                            <Button variant="ghost" size="lg" className="text-white hover:bg-white/10 rounded-2xl">
                                Learn More
                            </Button>
                        </Link>
                    </motion.div>
                </div>

                <div className="hidden lg:block absolute right-0 bottom-0 w-1/2 h-full">
                    {/* Decorative elements or product image could go here */}
                    <div className="absolute bottom-0 right-12 w-[450px] aspect-[4/5] bg-surface-50/5 rounded-t-[100px] border-x border-t border-white/10 overflow-hidden backdrop-blur-sm p-4">
                        <div className="w-full h-full rounded-t-[80px] bg-gradient-to-b from-white/10 to-transparent flex items-center justify-center">
                            <ShoppingBag size={120} className="text-white/20" />
                        </div>
                    </div>
                </div>
            </section>

            {/* Categories Grid */}
            <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                    { name: "Running", icon: TrendingUp, color: "bg-blue-500/10 text-blue-500", count: "12 Items" },
                    { name: "Athleisure", icon: Zap, color: "bg-orange-500/10 text-orange-500", count: "8 Items" },
                    { name: "Accessories", icon: ShoppingBag, color: "bg-purple-500/10 text-purple-500", count: "15 Items" }
                ].map((cat, idx) => (
                    <Link key={idx} to={`/products?category=${cat.name.toLowerCase()}`} className="group p-8 rounded-[32px] border border-line hover:border-brand transition-all bg-white hover:shadow-premium">
                        <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center mb-6", cat.color)}>
                            <cat.icon size={24} />
                        </div>
                        <h3 className="text-xl font-bold mb-1">{cat.name}</h3>
                        <p className="text-sm text-slate-500">{cat.count}</p>
                    </Link>
                ))}
            </section>

            {/* Featured Products */}
            <section className="space-y-8">
                <div className="flex items-end justify-between">
                    <div className="space-y-2">
                        <h2 className="text-4xl font-bold">Featured <span className="text-brand">Arrivals</span></h2>
                        <p className="text-slate-500">Handpicked highlights from our collection</p>
                    </div>
                    <Link to="/products" className="text-sm font-bold text-brand flex items-center gap-1 hover:underline">
                        View All <ArrowRight size={16} />
                    </Link>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                    {isLoading ? (
                        Array(4).fill(0).map((_, i) => (
                            <div key={i} className="space-y-4">
                                <Skeleton className="aspect-square rounded-2xl" />
                                <Skeleton className="h-4 w-2/3" />
                                <Skeleton className="h-4 w-1/2" />
                            </div>
                        ))
                    ) : (
                        products.map((p) => (
                            <ProductCard key={p.id} product={p} />
                        ))
                    )}
                </div>
            </section>
        </div>
    );
};

export { HomePage };
