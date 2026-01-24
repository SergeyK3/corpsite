import "../styles/globals.css";

export const metadata = {
  title: "Corpsite LK (MVP)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
