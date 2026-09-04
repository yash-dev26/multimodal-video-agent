import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px'
      }
    },
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        display: ['"Rajdhani"', '"JetBrains Mono"', 'sans-serif'],
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        // Obsidian base — the dark, near-black surface of the interface
        obsidian: {
          950: '#08080A',
          925: '#0D0C0E',
          900: '#131214',
          850: '#1A1816',
          800: '#211E1A',
          700: '#2C2822',
        },
        // Xenonite gold — refined metallic accent, used sparingly
        gold: {
          600: '#A9843A',
          500: '#C9A24E',
          400: '#D9B76B',
          300: '#E8CB93',
          200: '#F2E0BC',
        },
        // Warm ink — off-white text tuned warm rather than stark white
        ink: {
          100: '#EDE6D8',
          400: '#B4AA9B',
          600: '#7C7364',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)'
      },
      boxShadow: {
        'glass': '0 20px 60px -20px rgba(0, 0, 0, 0.65), inset 0 1px 0 0 rgba(232, 203, 147, 0.08)',
        'glow-gold': '0 0 0 1px rgba(201, 162, 78, 0.35), 0 8px 30px -8px rgba(201, 162, 78, 0.25)',
        'glow-gold-sm': '0 0 16px -2px rgba(201, 162, 78, 0.35)',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        // Slow, smooth breathing glow — used in place of blinking/bouncing
        // indicators anywhere the interface needs to show "in progress".
        breathe: {
          '0%, 100%': { opacity: '0.45' },
          '50%': { opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out',
        'breathe': 'breathe 2.4s ease-in-out infinite',
        'shimmer': 'shimmer 2.6s linear infinite',
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
