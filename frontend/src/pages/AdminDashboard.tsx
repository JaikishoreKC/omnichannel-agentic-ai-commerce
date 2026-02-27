import React from "react";
import {
    Users,
    Package,
    ShoppingCart,
    TrendingUp,
    Search,
    Plus,
    MoreVertical,
    ArrowUpRight,
    Settings as SettingsIcon,
    Activity
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";

const AdminDashboard: React.FC = () => {
    const stats = [
        { label: "Total Revenue", value: "$12,450.00", trend: "+12.5%", icon: TrendingUp },
        { label: "Active Users", value: "1,240", trend: "+3.2%", icon: Users },
        { label: "Pending Orders", value: "14", trend: "-2", icon: ShoppingCart },
        { label: "Products", value: "48", trend: "0", icon: Package }
    ];

    return (
        <div className="space-y-10 animate-fade-in">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                    <h1 className="text-4xl font-bold mb-2">Admin <span className="text-brand">Center</span></h1>
                    <p className="text-slate-500">System overview and commerce management</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button variant="outline" className="rounded-xl gap-2">
                        <SettingsIcon size={18} /> Settings
                    </Button>
                    <Button className="rounded-xl gap-2 shadow-lg">
                        <Plus size={18} /> New Product
                    </Button>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {stats.map((stat, i) => (
                    <div key={i} className="premium-card space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center text-slate-600">
                                <stat.icon size={20} />
                            </div>
                            <Badge variant={stat.trend.startsWith("+") ? "success" : stat.trend === "0" ? "secondary" : "danger"} className="rounded-lg">
                                {stat.trend}
                            </Badge>
                        </div>
                        <div>
                            <p className="text-sm text-slate-500 font-medium">{stat.label}</p>
                            <h3 className="text-2xl font-bold text-ink">{stat.value}</h3>
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Recent Orders Table Mockup */}
                <div className="lg:col-span-2 premium-card">
                    <div className="flex items-center justify-between mb-8">
                        <h3 className="text-xl font-bold">Recent Interactions</h3>
                        <div className="flex items-center gap-2">
                            <Input placeholder="Filter..." className="h-9 text-xs w-48" />
                            <Button variant="ghost" size="icon" className="h-9 w-9"><Activity size={16} /></Button>
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="border-b border-line text-xs font-bold text-slate-400 uppercase tracking-wider">
                                    <th className="pb-4 px-2">Order ID</th>
                                    <th className="pb-4 px-2">Customer</th>
                                    <th className="pb-4 px-2">Status</th>
                                    <th className="pb-4 px-2 text-right">Amount</th>
                                    <th className="pb-4 px-2"></th>
                                </tr>
                            </thead>
                            <tbody className="text-sm">
                                {[1, 2, 3, 4, 5].map((i) => (
                                    <tr key={i} className="border-b border-line/50 hover:bg-surface-50 transition-colors group">
                                        <td className="py-4 px-2 font-medium">#ORD-239{i}</td>
                                        <td className="py-4 px-2">
                                            <div className="flex flex-col">
                                                <span className="font-bold text-ink">User {i}</span>
                                                <span className="text-xs text-slate-400 tracking-tight">customer{i}@example.com</span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-2">
                                            <Badge variant={i % 2 === 0 ? "success" : "warning"}>
                                                {i % 2 === 0 ? "Delivered" : "Processing"}
                                            </Badge>
                                        </td>
                                        <td className="py-4 px-2 text-right font-display font-bold text-ink">$249.00</td>
                                        <td className="py-4 px-2 text-right">
                                            <button className="p-2 text-slate-300 group-hover:text-ink transition-colors">
                                                <MoreVertical size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="mt-6 flex justify-center">
                        <Button variant="ghost" size="sm" className="text-brand font-bold">View full register</Button>
                    </div>
                </div>

                {/* System Health / Agents */}
                <div className="space-y-8">
                    <div className="premium-card">
                        <h3 className="text-lg font-bold mb-6">AI Agent Status</h3>
                        <div className="space-y-4">
                            {[
                                { name: "Orchestrator", status: "Active", uptime: "99.9%" },
                                { name: "LoyaltyAgent", status: "Active", uptime: "100%" },
                                { name: "GeneralAnswer", status: "Active", uptime: "99.8%" }
                            ].map((agent, i) => (
                                <div key={i} className="flex items-center justify-between p-3 rounded-2xl bg-surface-50 border border-line">
                                    <div className="flex items-center gap-3">
                                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                        <span className="font-bold text-sm">{agent.name}</span>
                                    </div>
                                    <span className="text-xs text-slate-400">{agent.uptime}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="premium-card bg-brand text-white">
                        <h3 className="text-lg font-bold mb-2">Export Data</h3>
                        <p className="text-xs opacity-70 mb-6">Download your interaction history and sales records.</p>
                        <div className="space-y-3">
                            <Button className="w-full bg-white text-ink hover:bg-white/90 rounded-xl py-2 h-10 text-xs">
                                Download CSV
                            </Button>
                            <Button variant="ghost" className="w-full text-white hover:bg-white/10 rounded-xl py-2 h-10 text-xs">
                                API Access
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export { AdminDashboard };
