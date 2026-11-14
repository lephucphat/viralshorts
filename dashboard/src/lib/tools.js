import { Image } from 'lucide-react';

// The older tools kept under "Tools": each one is a tab of the original workspace.
// AI Shorts (fal.ai) and the gallery of its videos are left out on purpose: they need
// paid fal.ai access, so showing them would only lead people to an error. Add the two
// entries back ('saasshorts', 'ugc-gallery') once a fal.ai key is configured.
export const TOOLS = [
  { id: 'thumbnails', icon: Image, name: 'tools.studio', desc: 'tools.studio.desc' },
];
