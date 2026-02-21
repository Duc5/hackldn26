interface ErrorBannerProps {
  message: string;
}

export function ErrorBanner({ message }: ErrorBannerProps): JSX.Element {
  return <div className="error-banner">{message}</div>;
}
