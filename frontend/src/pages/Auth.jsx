import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Eye, EyeOff, AlertCircle, ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";

export default function Auth() {
  const location = useLocation();
  const navigate = useNavigate();
  const { login, signup } = useAuth();

  // Mode derived from URL: true if on /signup, false if on /login
  const isSignup = location.pathname === "/signup";

  const handleToggleMode = (targetMode) => {
    navigate(targetMode === "signup" ? "/signup" : "/login");
  };

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginShowPassword, setLoginShowPassword] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [loginSubmitting, setLoginSubmitting] = useState(false);

  // Signup form state
  const [workspaceName, setWorkspaceName] = useState("");
  const [signupName, setSignupName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [signupShowPassword, setSignupShowPassword] = useState(false);
  const [signupError, setSignupError] = useState("");
  const [signupSubmitting, setSignupSubmitting] = useState(false);

  const showDemoLogins = import.meta.env.VITE_SHOW_DEMO_LOGINS === "true";

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoginError("");
    setLoginSubmitting(true);
    try {
      await login(loginEmail, loginPassword);
      navigate("/app/dashboard");
    } catch (err) {
      setLoginError(err.message || "Invalid email or password");
    } finally {
      setLoginSubmitting(false);
    }
  };

  const handleSignupSubmit = async (e) => {
    e.preventDefault();
    setSignupError("");

    if (signupPassword.length < 10) {
      setSignupError("Password must be at least 10 characters long.");
      return;
    }

    if (signupPassword !== confirmPassword) {
      setSignupError("Passwords do not match.");
      return;
    }

    setSignupSubmitting(true);
    try {
      await signup(workspaceName, signupName, signupEmail, signupPassword);
      navigate("/app/dashboard");
    } catch (err) {
      setSignupError(err.message || "Failed to create workspace. Please try again.");
    } finally {
      setSignupSubmitting(false);
    }
  };

  const handleQuickLogin = (demoEmail, demoPassword) => {
    setLoginEmail(demoEmail);
    setLoginPassword(demoPassword);
    setLoginError("");
  };

  return (
    <div className="min-h-screen bg-canvas flex flex-col items-center justify-center p-3 sm:p-5 md:p-6 py-16 sm:py-20 font-sans relative overflow-hidden">
      {/* Blurred auth.png Background Layer */}
      <div
        className="fixed -inset-6 z-0 bg-[url('/auth.png')] bg-cover bg-center bg-no-repeat pointer-events-none filter blur-lg md:blur-xl scale-110"
        style={{ backgroundImage: "url('/auth.png')" }}
      />
      {/* Soft light tint for contrast */}
      <div className="fixed inset-0 z-0 bg-white/15 pointer-events-none" />
      {/* Dynamic Sliding Animation Styles */}
      <style>{`
        @media (min-width: 768px) {
          .auth-form-panel {
            transform: ${isSignup ? "translateX(78.57%)" : "translateX(0%)"};
            transition: transform 700ms cubic-bezier(0.4, 0, 0.2, 1);
          }
          .auth-image-panel {
            transform: ${isSignup ? "translateX(0%)" : "translateX(127.27%)"};
            transition: transform 700ms cubic-bezier(0.4, 0, 0.2, 1);
          }
        }
      `}</style>

      {/* Top Left Logo (Outside auth box, consistent with Landing page) */}
      <header className="absolute top-0 inset-x-0 z-40 bg-transparent h-16 sm:h-20">
        <div className="max-w-[1200px] mx-auto px-6 lg:px-8 h-full flex items-center">
          <Link to="/" className="flex items-center">
            <img
              src="/logo.png"
              alt="TARA"
              className="h-10 w-auto object-contain"
            />
          </Link>
        </div>
      </header>

      {/* Main Sliding Card Container */}
      <div className="w-full max-w-[780px] bg-surface-card border border-hairline rounded-2xl shadow-soft overflow-hidden relative z-10 my-auto min-h-[520px] md:h-[520px]">
        
        {/* ============================================================== */}
        {/* FORM PANEL: Slides between Left (Signin) and Right (Signup)    */}
        {/* ============================================================== */}
        <div className="auth-form-panel w-full md:w-[56%] h-full md:absolute md:top-0 md:left-0 z-10">
          
          {/* Sign In Form */}
          <div
            className={`p-6 sm:p-7 md:p-8 flex flex-col justify-center h-full transition-all duration-500 ease-in-out ${
              !isSignup
                ? "opacity-100 translate-x-0 pointer-events-auto visible"
                : "opacity-0 -translate-x-6 pointer-events-none invisible absolute inset-0 hidden md:flex"
            }`}
          >
            <div>
              <div className="mb-4">
                <h1 className="text-2xl font-bold font-serif text-ink mb-1">
                  Sign in to your workspace
                </h1>
                <p className="t-body-sm text-muted">
                  Enter your institutional credentials to access borrower registries.
                </p>
              </div>

              {loginError && (
                <div className="mb-3 p-2.5 rounded-md bg-red-50 border border-semantic-error/20 flex items-start gap-2 t-caption text-semantic-error">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{loginError}</span>
                </div>
              )}

              <form onSubmit={handleLoginSubmit} className="space-y-3">
                <div>
                  <label className="block t-caption text-body-strong mb-1" htmlFor="login-email-input">
                    Work email
                  </label>
                  <input
                    id="login-email-input"
                    type="email"
                    required
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="name@bank.com"
                    className="input-base py-2 px-3 text-sm"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block t-caption text-body-strong" htmlFor="login-password-input">
                      Password
                    </label>
                    <a
                      href="#forgot"
                      onClick={(e) => {
                        e.preventDefault();
                        alert("Please contact your workspace administrator to reset institutional credentials.");
                      }}
                      className="t-micro text-muted hover:text-ink underline underline-offset-2"
                    >
                      Forgot password?
                    </a>
                  </div>
                  <div className="relative">
                    <input
                      id="login-password-input"
                      type={loginShowPassword ? "text" : "password"}
                      required
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="input-base py-2 px-3 pr-9 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setLoginShowPassword(!loginShowPassword)}
                      className="absolute right-2.5 top-2.5 text-muted hover:text-ink"
                      title={loginShowPassword ? "Hide password" : "Show password"}
                    >
                      {loginShowPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-0.5">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      className="w-3.5 h-3.5 rounded border-hairline text-ink focus:ring-ink"
                      defaultChecked
                    />
                    <span className="t-caption text-muted">Remember workstation</span>
                  </label>
                  <span className="t-micro text-muted-soft flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span>256-bit TLS</span>
                  </span>
                </div>

                <Button
                  id="login-submit-btn"
                  type="submit"
                  disabled={loginSubmitting}
                  variant="primary"
                  size="md"
                  className="w-full mt-2 py-2 text-sm font-medium"
                >
                  {loginSubmitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Signing in...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </Button>
              </form>

              {/* Demo Accounts */}
              {showDemoLogins && (
                <div className="mt-3.5 pt-3 border-t border-hairline">
                  <span className="t-micro text-muted block mb-1.5 font-medium">Demo accounts:</span>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => handleQuickLogin("admin@apexbank.com", "ChangeMe123!")}
                      className="text-left px-2.5 py-1 rounded hover:bg-surface-strong border border-hairline text-xs text-body transition-colors"
                    >
                      <span className="font-semibold text-ink block">Apex Bank</span>
                      <span className="text-muted text-[11px]">admin</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleQuickLogin("employee@otherbank.com", "ChangeMe123!")}
                      className="text-left px-2.5 py-1 rounded hover:bg-surface-strong border border-hairline text-xs text-body transition-colors"
                    >
                      <span className="font-semibold text-ink block">Other Bank</span>
                      <span className="text-muted text-[11px]">employee</span>
                    </button>
                  </div>
                </div>
              )}

              <div className="mt-3.5 pt-3 border-t border-hairline t-caption text-muted">
                Don't have a workspace?{" "}
                <button
                  id="toggle-to-signup-btn"
                  type="button"
                  onClick={() => handleToggleMode("signup")}
                  className="text-ink t-body-strong underline underline-offset-4 hover:text-body cursor-pointer font-medium"
                >
                  Create workspace
                </button>
              </div>
            </div>
          </div>

          {/* Sign Up Form */}
          <div
            className={`p-6 sm:p-7 md:p-8 flex flex-col justify-center h-full transition-all duration-500 ease-in-out ${
              isSignup
                ? "opacity-100 translate-x-0 pointer-events-auto visible"
                : "opacity-0 translate-x-6 pointer-events-none invisible absolute inset-0 hidden md:flex"
            }`}
          >
            <div>
              <div className="mb-3">
                <h1 className="text-2xl font-bold font-serif text-ink">Create your workspace</h1>
                <p className="t-body-sm text-muted">
                  Deploy an isolated tenant for portfolio scoring and outreach.
                </p>
              </div>

              {signupError && (
                <div className="mb-2 p-2 rounded-md bg-red-50 border border-semantic-error/20 flex items-start gap-2 t-caption text-semantic-error">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{signupError}</span>
                </div>
              )}

              <form onSubmit={handleSignupSubmit} className="space-y-2.5">
                <div>
                  <label className="block t-caption text-body-strong mb-1" htmlFor="signup-workspace-input">
                    Workspace / Institution Name
                  </label>
                  <input
                    id="signup-workspace-input"
                    type="text"
                    required
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    placeholder="e.g. Apex Regional Bank"
                    className="input-base py-1.5 px-3 text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div>
                    <label className="block t-caption text-body-strong mb-1" htmlFor="signup-name-input">
                      Your Full Name
                    </label>
                    <input
                      id="signup-name-input"
                      type="text"
                      required
                      value={signupName}
                      onChange={(e) => setSignupName(e.target.value)}
                      placeholder="e.g. Priya Sharma"
                      className="input-base py-1.5 px-3 text-sm"
                    />
                  </div>

                  <div>
                    <label className="block t-caption text-body-strong mb-1" htmlFor="signup-email-input">
                      Work Email
                    </label>
                    <input
                      id="signup-email-input"
                      type="email"
                      required
                      value={signupEmail}
                      onChange={(e) => setSignupEmail(e.target.value)}
                      placeholder="name@institution.com"
                      className="input-base py-1.5 px-3 text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div>
                    <label className="block t-caption text-body-strong mb-1" htmlFor="signup-password-input">
                      Password (min 10)
                    </label>
                    <div className="relative">
                      <input
                        id="signup-password-input"
                        type={signupShowPassword ? "text" : "password"}
                        required
                        value={signupPassword}
                        onChange={(e) => setSignupPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="input-base py-1.5 px-3 pr-9 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setSignupShowPassword(!signupShowPassword)}
                        className="absolute right-2.5 top-2.5 text-muted hover:text-ink"
                      >
                        {signupShowPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block t-caption text-body-strong mb-1" htmlFor="signup-confirm-password-input">
                      Confirm Password
                    </label>
                    <input
                      id="signup-confirm-password-input"
                      type={signupShowPassword ? "text" : "password"}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="input-base py-1.5 px-3 text-sm"
                    />
                  </div>
                </div>

                <Button
                  id="signup-submit-btn"
                  type="submit"
                  disabled={signupSubmitting}
                  variant="primary"
                  size="md"
                  className="w-full mt-2 py-2 text-sm font-medium"
                >
                  {signupSubmitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Creating workspace...</span>
                    </>
                  ) : (
                    <>
                      <span>Create Workspace</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </Button>
              </form>

              <div className="mt-3.5 pt-3 border-t border-hairline t-caption text-muted">
                Already have an active workspace?{" "}
                <button
                  id="toggle-to-login-btn"
                  type="button"
                  onClick={() => handleToggleMode("login")}
                  className="text-ink t-body-strong underline underline-offset-4 hover:text-body cursor-pointer font-medium"
                >
                  Sign in
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ============================================================== */}
        {/* IMAGE SHOWCASE PANEL: Slides between Right (Signin) and Left (Signup) */}
        {/* ============================================================== */}
        <div
          className="auth-image-panel hidden md:flex md:w-[44%] h-full absolute top-0 left-0 z-20 overflow-hidden bg-[#e8f6f7] bg-[url('/auth.png')] bg-cover bg-center"
          style={{ backgroundImage: "url('/auth.png')" }}
        >
          {/* Hairline Divider Border (Left border when on right; Right border when on left) */}
          <div
            className={`absolute inset-y-0 left-0 w-px bg-hairline transition-opacity duration-500 z-30 ${
              isSignup ? "opacity-0" : "opacity-100"
            }`}
          />
          <div
            className={`absolute inset-y-0 right-0 w-px bg-hairline transition-opacity duration-500 z-30 ${
              isSignup ? "opacity-100" : "opacity-0"
            }`}
          />

          {/* SIGNIN SHOWCASE VIEW (Text at Top, Cubes below) */}
          <div
            className={`absolute inset-0 p-6 sm:p-7 flex flex-col justify-start transition-opacity duration-500 ease-in-out ${
              !isSignup ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
            }`}
          >
            <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
              <img
                src="/login.png"
                alt="TARA Platform Showcase"
                className="w-full h-full object-cover object-bottom"
              />
            </div>

            <div className="relative z-10 bg-surface-card/90 backdrop-blur-md border border-hairline rounded-lg p-3.5 sm:p-4 shadow-soft">
              <p className="t-caption text-body leading-relaxed">
                "TARA bridges CRM data with automated phone dialogue, executing compliant outreach across regional Indian languages."
              </p>
            </div>
          </div>

          {/* SIGNUP SHOWCASE VIEW (Cubes at Top, Text at Bottom) */}
          <div
            className={`absolute inset-0 p-6 sm:p-7 flex flex-col justify-end transition-opacity duration-500 ease-in-out ${
              isSignup ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
            }`}
          >
            <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
              <img
                src="/signup.png"
                alt="TARA Platform Showcase"
                className="w-full h-full object-cover object-top"
              />
            </div>

            <div className="relative z-10 bg-surface-card/90 backdrop-blur-md border border-hairline rounded-lg p-3.5 sm:p-4 shadow-soft">
              <p className="t-caption text-body leading-relaxed">
                "Deploy an isolated institutional workspace to score borrower portfolios and launch autonomous vernacular voice outreach in minutes."
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
