// Supabase Auth Helper
class AuthClient {
    constructor() {
        this.supabase = null;
        this.initStarted = false;
    }

    async init() {
        if (this.supabase) return this.supabase;
        if (this.initStarted) return new Promise(resolve => {
            const check = setInterval(() => {
                if (this.supabase) {
                    clearInterval(check);
                    resolve(this.supabase);
                }
            }, 10);
        });

        this.initStarted = true;
        try {
            // Fetch credentials from public endpoint
            const res = await fetch('/api/auth/config');
            const config = await res.json();

            this.supabase = supabase.createClient(config.url, config.key);
            console.log("🔐 Supabase Auth Initialized");
            return this.supabase;
        } catch (e) {
            console.error("❌ Failed to init Supabase:", e);
        }
    }

    async signIn(email, password) {
        const client = await this.init();
        return await client.auth.signInWithPassword({ email, password });
    }

    async signOut() {
        const client = await this.init();
        await client.auth.signOut();
        window.location.href = '/login.html';
    }

    async getCurrentUser() {
        const client = await this.init();
        const { data: { user } } = await client.auth.getUser();
        return user;
    }

    async getSessionToken() {
        const client = await this.init();
        const { data: { session } } = await client.auth.getSession();
        return session?.access_token || null;
    }

    async guard() {
        const user = await this.getCurrentUser();
        if (!user && !window.location.pathname.endsWith('login.html')) {
            window.location.href = '/login.html';
        }
    }
}

const authClient = new AuthClient();
authClient.init(); // Pre-init
