import { useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Compass, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error(
      "404 Error: Celestial vector not found in Blip-A navigation database:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-obsidian-950 text-ink-100 font-mono p-4">
      <div className="text-center max-w-md p-8 rounded-2xl glass-panel">
        <Compass className="w-12 h-12 text-gold-400 mx-auto mb-4 animate-spin [animation-duration:8s]" />
        <h1 className="text-4xl font-display font-semibold mb-2 text-gold-300">404 // Void</h1>
        <p className="text-sm text-ink-400 mb-6">
          Celestial coordinates outside Blip-A sensor array range. No planetary bodies detected at this vector.
        </p>
        <Button asChild variant="default">
          <a href="/" className="inline-flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            <span>Return to Rendezvous Deck</span>
          </a>
        </Button>
      </div>
    </div>
  );
};

export default NotFound;



