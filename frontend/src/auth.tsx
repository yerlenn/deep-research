import { ClerkProvider, SignIn, SignUp, useAuth as useClerkAuth, UserButton } from "@clerk/clerk-react";
import { createContext, ReactNode, useContext } from "react";

type AuthContextValue = {
  isLoaded: boolean;
  isSignedIn: boolean;
  getToken: () => Promise<string | null>;
  userControl: ReactNode;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
const authDisabled = import.meta.env.VITE_AUTH_DISABLED === "true";
const clerkConfigured = Boolean(clerkKey);

function ClerkBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  return (
    <AuthContext.Provider
      value={{
        isLoaded,
        isSignedIn: Boolean(isSignedIn),
        getToken,
        userControl: <UserButton afterSignOutUrl="/" />
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (authDisabled) {
    return (
      <AuthContext.Provider
        value={{
          isLoaded: true,
          isSignedIn: true,
          getToken: async () => null,
          userControl: <div className="dev-user">Dev user</div>
        }}
      >
        {children}
      </AuthContext.Provider>
    );
  }

  if (!clerkConfigured) {
    return (
      <AuthContext.Provider
        value={{
          isLoaded: true,
          isSignedIn: false,
          getToken: async () => null,
          userControl: <a className="button" href="/sign-in">Sign in</a>
        }}
      >
        {children}
      </AuthContext.Provider>
    );
  }

  return (
    <ClerkProvider publishableKey={clerkKey!}>
      <ClerkBridge>{children}</ClerkBridge>
    </ClerkProvider>
  );
}

export function AuthPage({ mode }: { mode: "sign-in" | "sign-up" }) {
  if (authDisabled) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Auth is disabled locally</h1>
          <p>Set Clerk environment values to use real sign-in and sign-up routes.</p>
          <a className="button primary" href="/">
            Return to app
          </a>
        </div>
      </div>
    );
  }

  if (!clerkConfigured) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Clerk is not configured</h1>
          <p>Add `VITE_CLERK_PUBLISHABLE_KEY` in `frontend/.env` and Clerk backend values in `backend/.env` to enable sign-in.</p>
          <a className="button primary" href="/">
            Return to app
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      {mode === "sign-in" ? (
        <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" fallbackRedirectUrl="/" />
      ) : (
        <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/" />
      )}
    </div>
  );
}

export function useAppAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAppAuth must be used inside AuthProvider");
  }
  return value;
}
