import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Audit from "./pages/Audit";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Inbox from "./pages/Inbox";
import Settings from "./pages/Settings";
import Simulator from "./pages/Simulator";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/simulator" element={<Simulator />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/audit" element={<Audit />} />
      </Route>
    </Routes>
  );
}
