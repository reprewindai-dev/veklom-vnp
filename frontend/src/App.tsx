"use client";

import React, { lazy, Suspense } from 'react';
import { ArrowRight, Activity, Zap, Lock, Cpu, Mail, ShieldCheck } from 'lucide-react';
import { motion } from "framer-motion";

const NetworkTopologyPanel = lazy(() => import('./components/NetworkTopologyPanel'));

type VerificationStackItem = {
  section: string;
  status: string;
};

type VnpPublicManifest = {
  verification_stack?: VerificationStackItem[];
};

const fallbackVerificationStack: VerificationStackItem[] = [
  { section: 'Physical measurements', status: 'Disconnected' },
  { section: 'Signed telemetry', status: 'Disconnected' },
  { section: 'Route beacons', status: 'Disconnected' },
  { section: 'Robust scoring', status: 'Disconnected' },
  { section: 'x402 settlement evidence', status: 'Disconnected' },
  { section: 'PGL audit trails', status: 'Disconnected' },
  { section: 'Agent/runtime enforcement', status: 'Auth Required' },
];

const fadeUpVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } }
} as any;

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const VEKLOM_URL = "https://veklom.com";
const VNP_GITHUB_URL = "https://github.com/reprewindai-dev/veklom-vnp";

export default function VNPLandingPage() {
  const [verificationStack, setVerificationStack] = React.useState<VerificationStackItem[]>(fallbackVerificationStack);

  React.useEffect(() => {
    let cancelled = false;

    async function loadVerificationStack() {
      try {
        const response = await fetch('/api/vnp.json', {
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) return;
        const manifest = (await response.json()) as VnpPublicManifest;
        if (!cancelled && manifest.verification_stack?.length) {
          setVerificationStack(manifest.verification_stack);
        }
      } catch {
        // Keep conservative fallback statuses if backend-derived manifest is unavailable.
      }
    }

    loadVerificationStack();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen bg-[#0A0A0A] text-white overflow-x-hidden selection:bg-[#FFB800]/30 relative z-10 font-sans">
      
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#0A0A0A]/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#FFB800] rounded flex items-center justify-center brand-glow">
              <span className="font-bold text-black leading-none">V</span>
            </div>
            <span className="font-bold tracking-wider text-lg font-mono">VEKLOM<span className="text-gray-500">_VNP</span></span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-gray-400">
            <a href="#protocol" className="hover:text-white transition-colors">The Protocol</a>
            <a href="#methodology" className="hover:text-white transition-colors">Methodology</a>
            <a href="#network" className="hover:text-white transition-colors">Global Mesh</a>
            <a href={`${VEKLOM_URL}/vnp/docs`} className="hover:text-white transition-colors">Documentation</a>
          </div>
          <div className="flex items-center gap-6 text-sm font-medium">
            <a href={`${VEKLOM_URL}/workspace`} className="text-gray-400 hover:text-white transition-colors">Access Workspace</a>
            <a href={`${VEKLOM_URL}/signup`} className="bg-white text-black px-4 py-2 rounded-md hover:bg-gray-200 transition-colors">
              Deploy Agent
            </a>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 lg:pt-40 lg:pb-32 px-6 overflow-hidden">
        <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[10%] left-[50%] -translate-x-1/2 w-[1000px] h-[500px] bg-[#FFB800]/15 blur-[120px] rounded-full opacity-50 mix-blend-screen" />
        </div>
        
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="max-w-4xl mx-auto text-center relative z-10"
        >
          <motion.div variants={fadeUpVariants} className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#FFB800]/10 border border-[#FFB800]/20 text-[#FFB800] text-xs font-semibold uppercase tracking-wider mb-8">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            VNP Methodology v1.0
          </motion.div>
          
          <motion.h1 variants={fadeUpVariants} className="text-5xl lg:text-7xl font-bold tracking-tight mb-6 leading-tight">
            Cryptographically Verifiable <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-[#FFE6A8] to-[#FFB800]">
              Telemetry for the M2M Economy.
            </span>
          </motion.h1>
          
          <motion.p variants={fadeUpVariants} className="text-xl text-gray-400 mb-10 max-w-3xl mx-auto leading-relaxed">
            Autonomous AI agents require absolute deterministic reliability. Standard status pages are marketing tools. The Veklom Nexus Protocol provides mathematical proof of API uptime, latency, and compliance across a decentralized global mesh.
          </motion.p>
          
          <motion.div variants={fadeUpVariants} className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a href={`${VEKLOM_URL}/vnp/docs`} className="w-full sm:w-auto px-8 py-4 rounded-lg bg-white text-black font-bold text-lg hover:bg-gray-200 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-white/5">
              Open Docs Hub <ArrowRight className="w-5 h-5" />
            </a>
            <a href={`${VEKLOM_URL}/vnp/methodology`} className="w-full sm:w-auto px-8 py-4 rounded-lg bg-white/5 border border-white/10 text-white font-bold text-lg hover:bg-white/10 transition-colors flex items-center justify-center">
              Read the Methodology
            </a>
          </motion.div>
        </motion.div>
      </section>

      {/* Why VNP Section */}
      <section id="protocol" className="py-24 px-6 border-t border-white/5 bg-[#0B0B0D] relative scroll-mt-16">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16 max-w-3xl mx-auto">
            <span className="inline-flex items-center gap-1 text-[#FFB800] text-xs font-bold uppercase tracking-widest bg-[#FFB800]/5 border border-[#FFB800]/10 px-3 py-1 rounded-full mb-4">
              <Activity className="w-3 h-3" /> System Vulnerabilities
            </span>
            <h2 className="text-4xl font-extrabold tracking-tight mb-6">Why API Benchmarking is Critical Today</h2>
            <p className="text-gray-400 max-w-2xl mx-auto text-lg leading-relaxed">
              We are transitioning from human-driven interfaces to autonomous agentic routing. In a world where AI orchestrates thousands of API calls per second, silent degradation is fatal.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="card obsidian-glass p-8 flex flex-col justify-between hover:border-[#FFB800]/30 transition-all group duration-300">
              <div className="w-12 h-12 rounded-xl bg-[#FFB800]/10 flex items-center justify-center border border-[#FFB800]/20 mb-6 group-hover:bg-[#FFB800]/20 group-hover:border-[#FFB800]/40 transition-colors duration-300">
                <Cpu className="w-6 h-6 text-[#FFB800]" />
              </div>
              <h3 className="text-xl font-bold mb-3">Agentic Web Routing</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                When an AI agent chooses an LLM or financial provider, it requires millisecond-accurate latency maps. VNP provides the oracle data required for intelligent fallback and automated failover.
              </p>
            </div>
            
            <div className="card obsidian-glass p-8 flex flex-col justify-between hover:border-[#FFB800]/30 transition-all group duration-300">
              <div className="w-12 h-12 rounded-xl bg-[#FFB800]/10 flex items-center justify-center border border-[#FFB800]/20 mb-6 group-hover:bg-[#FFB800]/20 group-hover:border-[#FFB800]/40 transition-colors duration-300">
                <ShieldCheck className="w-6 h-6 text-[#FFB800]" />
              </div>
              <h3 className="text-xl font-bold mb-3">Zero-Trust Telemetry</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Do not trust provider-controlled status pages. VNP uses decentralized Edge Probes that execute 4-phase network timings (DNS, TCP, TLS, TTFB) and sign the results using Ed25519 cryptography.
              </p>
            </div>

            <div className="card obsidian-glass p-8 flex flex-col justify-between hover:border-[#FFB800]/30 transition-all group duration-300">
              <div className="w-12 h-12 rounded-xl bg-[#FFB800]/10 flex items-center justify-center border border-[#FFB800]/20 mb-6 group-hover:bg-[#FFB800]/20 group-hover:border-[#FFB800]/40 transition-colors duration-300">
                <Lock className="w-6 h-6 text-[#FFB800]" />
              </div>
              <h3 className="text-xl font-bold mb-3">SLA Performance Bonds</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                VNP connects real x402 USDC route payments to BYOS settlement evidence, so autonomous clients can route against receipts instead of provider-controlled claims.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Methodology Section */}
      <section id="methodology" className="py-24 px-6 border-t border-white/5 bg-[#0A0A0C] relative scroll-mt-16">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="space-y-8">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FFB800]/10 border border-[#FFB800]/20 text-[#FFB800] text-sm font-medium font-mono">
                VNP Methodology v1.0 - UPDATED JULY 7
              </div>
              <h2 className="text-4xl font-extrabold tracking-tight leading-tight">
                VNP v1.0 Verification Stack
              </h2>
              <p className="text-gray-400 text-lg leading-relaxed">
                To prevent manipulation, VNP evaluates API trust through physical measurements, signed telemetry, route beacons, robust scoring, x402 settlement evidence, PGL audit trails, and agent/runtime enforcement.
              </p>
              
              <div className="space-y-4">
                {verificationStack.map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10 hover:border-[#FFB800]/30 transition-colors">
                    <span className="font-medium text-gray-300">{item.section}</span>
                    <span className="font-mono text-[#FFB800] font-bold">{item.status}</span>
                  </div>
                ))}
              </div>
            </div>
            
            <div id="network" className="relative scroll-mt-24">
              <div className="absolute -inset-4 bg-gradient-to-r from-[#FFB800]/10 to-transparent blur-2xl opacity-50 rounded-3xl -z-10" />
              <div className="border border-white/10 rounded-2xl overflow-hidden bg-[#0A0A0A] shadow-2xl">
                <div className="p-4 border-b border-white/5 bg-white/[0.02] flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-xs font-mono text-gray-400">BACKEND VIEW: VNP_TOPOLOGY_MESH</span>
                </div>
                <div className="h-[500px] overflow-hidden p-6 relative bg-[#060608]">
                  <div className="transform scale-[0.85] origin-top-left w-[117%] h-[117%] pointer-events-none">
                    <Suspense fallback={<div className="h-[500px] bg-white/5 rounded-xl animate-pulse" />}>
                      <NetworkTopologyPanel />
                    </Suspense>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32 border-t border-white/5 relative overflow-hidden bg-[#0A0A0A]">
        <div className="absolute inset-0 bg-[#FFB800]/5" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#FFB800]/10 blur-[100px] rounded-full pointer-events-none" />
        
        <div className="max-w-4xl mx-auto text-center relative z-10 px-6">
          <h2 className="text-4xl md:text-5xl font-extrabold mb-6">Standardize Your Infrastructure</h2>
          <p className="text-xl text-gray-400 mb-6">
            Not all APIs belong on VNP. We exclusively measure mission-critical endpoints for the <strong className="text-white">Machine-to-Machine (M2M) Economy</strong>.
          </p>
          
          <div className="grid md:grid-cols-2 gap-6 text-left mb-12 max-w-3xl mx-auto">
            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <h3 className="text-[#FFB800] font-bold mb-3 flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-[#FFB800]" /> VNP Worthy (Tier 1)</h3>
              <ul className="space-y-2 text-sm text-gray-400">
                <li>• <strong className="text-gray-300">AI Infrastructure:</strong> LLMs, Vector DBs, Tools</li>
                <li>• <strong className="text-gray-300">Financial & Web3:</strong> Payments, Blockchain RPCs</li>
                <li>• <strong className="text-gray-300">Core Telecom:</strong> SMS, Email, Routing Oracles</li>
              </ul>
            </div>
            <div className="bg-red-500/5 border border-red-500/10 rounded-xl p-6">
              <h3 className="text-red-400 font-bold mb-3 flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-400" /> Not Supported</h3>
              <ul className="space-y-2 text-sm text-gray-400">
                <li>• Standard blogs or content feeds</li>
                <li>• Hobbyist or non-commercial APIs</li>
                <li>• Internal private endpoints with no public SLA</li>
              </ul>
            </div>
          </div>

          <a href={`${VEKLOM_URL}/vnp/claim`} className="inline-flex px-10 py-5 rounded-lg bg-white text-black font-bold text-lg hover:bg-gray-200 transition-colors items-center gap-2 shadow-lg shadow-white/5">
            Submit API for VNP Evaluation <Zap className="w-5 h-5" />
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-white/5 bg-[#0A0A0C] text-sm text-gray-500">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-12 mb-12">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-6 h-6 bg-[#FFB800] rounded flex items-center justify-center">
                <span className="font-bold text-black text-xs leading-none">V</span>
              </div>
              <span className="font-bold text-white font-mono tracking-wider">VEKLOM<span className="text-gray-500">_VNP</span></span>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed mb-6">
              The cryptographic standard for M2M API telemetry. Governing the autonomous web with mathematical certainty.
            </p>
          </div>
          
          <div>
            <h4 className="font-bold mb-4 text-gray-300">Protocol</h4>
            <ul className="space-y-3">
              <li><a href={`${VEKLOM_URL}/vnp/methodology`} className="hover:text-white transition-colors">VNP Methodology v1.0</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/governance`} className="hover:text-white transition-colors">Governance Charter</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/slashing`} className="hover:text-white transition-colors">Slashing Mechanics</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/x402`} className="hover:text-white transition-colors">x402 Settlement</a></li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-bold mb-4 text-gray-300">Developers</h4>
            <ul className="space-y-3">
              <li><a href={`${VEKLOM_URL}/vnp/docs`} className="hover:text-white transition-colors">Documentation</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/sdk/python`} className="hover:text-white transition-colors">Python Probe SDK</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/sdk/fastapi`} className="hover:text-white transition-colors">FastAPI Integration</a></li>
              <li><a href={VNP_GITHUB_URL} className="hover:text-white transition-colors">GitHub Repository</a></li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-bold mb-4 text-gray-300">Network</h4>
            <ul className="space-y-3">
              <li><a href={`${VEKLOM_URL}/vnp/topology`} className="hover:text-white transition-colors">Global Topology Map</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/operators`} className="hover:text-white transition-colors">Node Operator Guide</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/directory`} className="hover:text-white transition-colors">API Directory</a></li>
              <li><a href={`${VEKLOM_URL}/vnp/status`} className="hover:text-white transition-colors">Status & Uptime</a></li>
            </ul>
          </div>
        </div>
        
        <div className="max-w-7xl mx-auto px-6 border-t border-white/5 pt-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <p>© {new Date().getFullYear()} Veklom Corporation. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <a href="mailto:support@veklom.com" className="hover:text-white transition-colors flex items-center gap-1"><Mail className="w-3.5 h-3.5" /> support@veklom.com</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
