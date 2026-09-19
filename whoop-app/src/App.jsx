import { Routes, Route } from 'react-router-dom';
import Shell from './components/Shell';
import Home from './screens/Home';
import Health from './screens/Health';
import Community from './screens/Community';
import More from './screens/More';
import Chat from './screens/Chat';
import Cognitive from './screens/Cognitive';

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<Home />} />
        <Route path="/health" element={<Health />} />
        <Route path="/community" element={<Community />} />
        <Route path="/more" element={<More />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/cognitive" element={<Cognitive />} />
      </Route>
    </Routes>
  );
}
