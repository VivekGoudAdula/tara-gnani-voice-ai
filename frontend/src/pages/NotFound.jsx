import React from "react";
import { ArrowLeft } from "lucide-react";
import Button from "../components/Button";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-canvas flex flex-col items-center justify-center p-6 text-center font-sans">
      <div className="max-w-md">
        <span className="t-label text-muted-soft block mb-3">
          404 Error
        </span>
        <h1 className="t-display-xl text-ink mb-3">Page not found</h1>
        <p className="t-body-sm text-body mb-8">
          The requested address does not exist or has moved.
        </p>
        <Button
          to="/"
          variant="primary"
          size="md"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Homepage</span>
        </Button>
      </div>
    </div>
  );
}
