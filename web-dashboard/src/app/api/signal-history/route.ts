import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// Initialize Supabase client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

export async function GET() {
    try {
        // Fetch closed trades from execution_log
        // Using only columns that exist in the table
        const { data, error } = await supabase
            .from("execution_log")
            .select("id, created_at, type, direction, status, profit, entry_price, ticket, data")
            .eq("type", "TRADE")
            .eq("status", "CLOSED")
            .order("created_at", { ascending: false })
            .limit(10);

        if (error) {
            console.error("Supabase error:", error);
            return NextResponse.json({ error: error.message }, { status: 500 });
        }

        // Transform data for frontend
        // Extract pair from data object if available
        const trades = (data || []).map((trade) => ({
            id: trade.id,
            created_at: trade.created_at,
            pair: trade.data?.pair || trade.data?.symbol || "EUR/USD",
            direction: trade.direction || trade.data?.direction || "LONG",
            status: trade.status,
            profit: trade.profit || 0,
            entry_price: trade.entry_price || trade.data?.entry_price,
            close_price: trade.data?.close_price,
        }));

        return NextResponse.json({ trades });
    } catch (error) {
        console.error("API error:", error);
        return NextResponse.json(
            { error: "Failed to fetch signal history" },
            { status: 500 }
        );
    }
}
