import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  // No StrictMode: its double-mounted effects would open two interview sockets (two LLM sessions).
  <App />,
);
