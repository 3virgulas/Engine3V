import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

export async function GET() {
    try {
        const { data: trades, error } = await supabase
            .from('execution_log')
            .select('*')
            .order('created_at', { ascending: false })
            .limit(50);

        if (error) {
            console.error('Supabase error:', error);
            return NextResponse.json({ error: error.message }, { status: 500 });
        }

        return NextResponse.json({ trades });
    } catch (error) {
        console.error('Internal server error:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
