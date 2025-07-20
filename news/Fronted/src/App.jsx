import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './App.css';

// API Configuration
const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [inputMode, setInputMode] = useState('url');
  const [urlInput, setUrlInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [requestId, setRequestId] = useState(null);

  // Get today's date for edition line
  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const handleAnalyze = async () => {
    const content = inputMode === 'url' ? urlInput : textInput;
    if (!content) return;

    setIsLoading(true);
    setResults(null);
    setError(null);
    setAnalysisProgress(0);
    setRequestId(null);

    try {
      // Start analysis
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: content,
          analysis_type: inputMode
        })
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      setRequestId(data.request_id);

      // Poll for results
      await pollForResults(data.request_id);

    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  const pollForResults = async (id) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/results/${id}`);
        const data = await response.json();

        // Update progress
        setAnalysisProgress(Math.min((attempts / maxAttempts) * 100, 95));

        if (data.status === 'completed') {
          setResults(data);
          setAnalysisProgress(100);
          setIsLoading(false);
          return;
        } else if (data.status === 'error') {
          throw new Error(data.error_message || 'Analysis failed');
        }

        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 2000); // Poll every 2 seconds
        } else {
          throw new Error('Analysis timed out');
        }
      } catch (err) {
        setError(err.message);
        setIsLoading(false);
      }
    };

    poll();
  };

  const getScoreColor = (score) => {
    if (score >= 80) return '#10b981'; // Green
    if (score >= 60) return '#f59e0b'; // Yellow
    if (score >= 40) return '#f97316'; // Orange
    return '#ef4444'; // Red
  };

  const getScoreLabel = (score) => {
    if (score >= 80) return 'Highly Credible';
    if (score >= 60) return 'Credible';
    if (score >= 40) return 'Questionable';
    return 'Not Credible';
  };

  const getTierLabel = (tier) => {
    const tierLabels = {
      1: 'Highly Reliable',
      2: 'Reliable', 
      3: 'Moderate',
      4: 'Low Reliability',
      5: 'Very Low Reliability',
      'satire': 'Satire'
    };
    return tierLabels[tier] || 'Unknown';
  };

  return (
    <main className="min-h-screen bg-[#faf7f2] text-black font-serif p-4 md:p-8 lg:p-12 relative">
      {/* Torn top edge for realism */}
      <img src="/torn-top.png" alt="torn edge" style={{position:'absolute', top:0, left:0, width:'100%', zIndex:3, pointerEvents:'none'}} />
      
      <div className="w-full shadow-xl border border-gray-300 rounded-lg p-8 sm:p-12 newspaper-paper relative overflow-hidden" style={{background:'rgba(220,220,220,0.45)'}}>
        {/* Dog-ear crease for realism */}
        <div className="dog-ear-crease"></div>
        {/* Watermark */}
        <div className="newspaper-watermark">NEWS</div>
        
        {/* Masthead */}
        <div className="border-b-4 border-black pb-2 mb-2 text-center newspaper-masthead relative z-10 flex flex-col items-center">
          <span className="newspaper-crest">EST. 2024</span>
          <h1 className="text-5xl font-extrabold tracking-wide uppercase newspaper-masthead">THE VERACITY TIMES</h1>
          <div className="newspaper-edition">Published: {today} | Edition No. 1</div>
          <p className="italic text-lg text-gray-700 mt-1 font-serif">Your trusted source for news analysis</p>
        </div>

        {/* Input Mode Toggle */}
        <div className="flex flex-col items-center gap-2 mb-6 mt-4">
          <span className="font-semibold text-gray-700">Analyze Article From:</span>
          <div className="flex gap-2">
            <button
              className={`px-4 py-2 rounded-t-lg border-b-2 font-semibold transition-colors duration-150 ${inputMode === 'url' ? 'border-black bg-gray-100' : 'border-transparent bg-gray-200 text-gray-500'}`}
              onClick={() => setInputMode('url')}
            >
              URL
            </button>
            <button
              className={`px-4 py-2 rounded-t-lg border-b-2 font-semibold transition-colors duration-150 ${inputMode === 'text' ? 'border-black bg-gray-100' : 'border-transparent bg-gray-200 text-gray-500'}`}
              onClick={() => setInputMode('text')}
            >
              Text
            </button>
          </div>
        </div>

        {/* Input Section */}
        <div className="mb-10">
          {inputMode === 'url' ? (
            <div className="flex gap-4">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="Paste a news article URL..."
                className="input-field border border-gray-400 bg-[#f5f5f5] text-black font-serif flex-1"
              />
              <button
                onClick={handleAnalyze}
                disabled={isLoading || !urlInput}
                className="button-primary bg-black text-white font-serif border border-gray-700 hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Analyzing...' : 'Analyze'}
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Paste or type news article text..."
                className="input-field border border-gray-400 bg-[#f5f5f5] text-black font-serif min-h-[100px] resize-vertical"
              />
              <button
                onClick={handleAnalyze}
                disabled={isLoading || !textInput}
                className="self-end button-primary bg-black text-white font-serif border border-gray-700 hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Analyzing...' : 'Analyze'}
              </button>
            </div>
          )}
        </div>

        {/* Error Display */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6"
            >
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Analysis Error</h3>
                  <div className="mt-2 text-sm text-red-700">{error}</div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Results Section */}
        <AnimatePresence>
          {(isLoading || results !== null) && (
            <div className="w-full flex flex-col items-center justify-center min-h-[520px]">
              {isLoading ? (
                <EnhancedLoadingSpinner progress={analysisProgress} requestId={requestId} />
              ) : results ? (
                <EnhancedResultsDisplay results={results} getScoreColor={getScoreColor} getScoreLabel={getScoreLabel} getTierLabel={getTierLabel} />
              ) : null}
            </div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}

const EnhancedLoadingSpinner = ({ progress, requestId }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="text-center p-8 w-full max-w-md"
  >
    <div className="relative">
      {/* Progress Circle */}
      <div className="relative h-32 w-32 mx-auto mb-6">
        <svg className="transform -rotate-90 w-32 h-32" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="8"
          />
          <motion.circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#3b82f6"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={2 * Math.PI * 45}
            strokeDashoffset={2 * Math.PI * 45 * (1 - progress / 100)}
            initial={{ strokeDashoffset: 2 * Math.PI * 45 }}
            animate={{ strokeDashoffset: 2 * Math.PI * 45 * (1 - progress / 100) }}
            transition={{ duration: 0.5 }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-gray-700">{Math.round(progress)}%</span>
        </div>
      </div>
      
      <div className="space-y-4">
        <div className="flex items-center justify-center space-x-2">
          <div className="h-3 w-3 bg-blue-500 rounded-full animate-pulse"></div>
          <div className="h-3 w-3 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
          <div className="h-3 w-3 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
        </div>
        
        <p className="text-lg font-semibold text-gray-700">Analyzing Article</p>
        <p className="text-sm text-gray-500">This may take a few minutes...</p>
        
        {requestId && (
          <div className="text-xs text-gray-400 bg-gray-100 rounded px-2 py-1 inline-block">
            ID: {requestId.slice(0, 8)}...
          </div>
        )}
      </div>
    </div>
  </motion.div>
);

const EnhancedResultsDisplay = ({ results, getScoreColor, getScoreLabel, getTierLabel }) => {
  const score = results.final_credibility_score;
  const color = getScoreColor(score);
  const label = getScoreLabel(score);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full space-y-8"
    >
      {/* Main Score Section */}
      <div className="text-center">
        <EnhancedScoreCircle score={score} color={color} label={label} />
      </div>

      {/* Score Components */}
      {results.score_components && (
        <ScoreComponentsBreakdown components={results.score_components} />
      )}

      {/* Publisher Information */}
      {results.publisher_tier && (
        <PublisherInfo tier={results.publisher_tier} getTierLabel={getTierLabel} />
      )}

      {/* Bias Report */}
      {results.bias_report && (
        <BiasReportSection biasReport={results.bias_report} />
      )}

      {/* Claim Verifications */}
      {results.claim_verifications && results.claim_verifications.length > 0 && (
        <ClaimVerificationsSection claims={results.claim_verifications} />
      )}

      {/* Processing Info */}
      <ProcessingInfo results={results} />
    </motion.div>
  );
};

const EnhancedScoreCircle = ({ score, color, label }) => {
  const [displayScore, setDisplayScore] = useState(0);
  
  useEffect(() => {
    const duration = 1500;
    const startTime = performance.now();
    
    function animate(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      setDisplayScore(Math.floor(progress * score));
      if (progress < 1) requestAnimationFrame(animate);
      else setDisplayScore(score);
    }
    animate(startTime);
  }, [score]);

  const circumference = 2 * Math.PI * 60;
  const progress = displayScore / 100;

  return (
    <div className="relative">
      <div className="relative h-80 w-80 mx-auto flex flex-col items-center justify-center">
        <svg className="transform -rotate-90 w-80 h-80" viewBox="0 0 200 200">
          <circle
            cx="100"
            cy="100"
            r="60"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="12"
          />
          <motion.circle
            cx="100"
            cy="100"
            r="60"
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - progress)}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - progress) }}
            transition={{ duration: 1.5, ease: "easeOut" }}
          />
        </svg>
        
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="flex items-end justify-center mb-2">
            <span className="text-8xl font-extrabold drop-shadow-lg" style={{ color }}>
              {displayScore}
            </span>
            <span className="text-4xl font-bold mb-2 ml-2" style={{ color }}>%</span>
          </div>
          <span className="text-2xl font-bold text-gray-800 mb-1">{label}</span>
          <span className="text-lg font-semibold text-gray-600">Credibility Score</span>
        </div>
      </div>
    </div>
  );
};

const ScoreComponentsBreakdown = ({ components }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.3 }}
    className="bg-white rounded-xl shadow-lg p-6 border border-gray-200"
  >
    <h3 className="text-xl font-bold text-gray-800 mb-4 text-center">Score Breakdown</h3>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {Object.entries(components).map(([key, value]) => (
        <div key={key} className="text-center">
          <div className="relative">
            <svg className="w-20 h-20 mx-auto mb-3" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="35"
                fill="none"
                stroke="#e5e7eb"
                strokeWidth="8"
              />
              <motion.circle
                cx="50"
                cy="50"
                r="35"
                fill="none"
                stroke={key === 'Source' ? '#3b82f6' : key === 'Evidence' ? '#10b981' : '#f59e0b'}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={2 * Math.PI * 35}
                strokeDashoffset={2 * Math.PI * 35 * (1 - value / 100)}
                initial={{ strokeDashoffset: 2 * Math.PI * 35 }}
                animate={{ strokeDashoffset: 2 * Math.PI * 35 * (1 - value / 100) }}
                transition={{ duration: 1, delay: 0.5 }}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-bold text-gray-700">{Math.round(value)}</span>
            </div>
          </div>
          <h4 className="font-semibold text-gray-800 mb-1">{key}</h4>
          <p className="text-sm text-gray-500">
            {key === 'Source' && 'Publisher reliability'}
            {key === 'Evidence' && 'Fact-checking results'}
            {key === 'Bias' && 'Content bias analysis'}
          </p>
        </div>
      ))}
    </div>
  </motion.div>
);

const PublisherInfo = ({ tier, getTierLabel }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.4 }}
    className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200"
  >
    <div className="flex items-center justify-between">
      <div>
        <h3 className="text-xl font-bold text-gray-800 mb-2">Publisher Reliability</h3>
        <p className="text-gray-600">Source credibility assessment</p>
      </div>
      <div className="text-right">
        <div className={`inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold ${
          tier <= 2 ? 'bg-green-100 text-green-800' :
          tier === 3 ? 'bg-yellow-100 text-yellow-800' :
          'bg-red-100 text-red-800'
        }`}>
          <span className="w-2 h-2 rounded-full mr-2 bg-current"></span>
          Tier {tier}: {getTierLabel(tier)}
        </div>
      </div>
    </div>
  </motion.div>
);

const BiasReportSection = ({ biasReport }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.5 }}
    className="bg-white rounded-xl shadow-lg p-6 border border-gray-200"
  >
    <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
      <svg className="w-6 h-6 mr-2 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
      Bias Analysis
    </h3>
    <div className="bg-gray-50 rounded-lg p-4">
      <p className="text-gray-700 leading-relaxed font-serif">{biasReport}</p>
    </div>
  </motion.div>
);

const ClaimVerificationsSection = ({ claims }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.6 }}
    className="bg-white rounded-xl shadow-lg p-6 border border-gray-200"
  >
    <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
      <svg className="w-6 h-6 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
      Claim Verifications ({claims.length})
    </h3>
    <div className="space-y-4">
      {claims.map((claim, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.7 + index * 0.1 }}
          className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
        >
          <div className="flex items-start justify-between mb-3">
            <h4 className="font-semibold text-gray-800 flex-1 mr-4">{claim.claim}</h4>
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
              claim.verdict === 'Well-Supported' ? 'bg-green-100 text-green-800' :
              claim.verdict === 'Partially Supported' ? 'bg-yellow-100 text-yellow-800' :
              claim.verdict === 'Lacks Evidence' ? 'bg-gray-100 text-gray-800' :
              claim.verdict === 'Disputed' ? 'bg-orange-100 text-orange-800' :
              'bg-red-100 text-red-800'
            }`}>
              {claim.verdict}
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-2">{claim.evidence_summary}</p>
          <p className="text-xs text-gray-500 italic">{claim.rationale}</p>
        </motion.div>
      ))}
    </div>
  </motion.div>
);

const ProcessingInfo = ({ results }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    transition={{ delay: 0.8 }}
    className="text-center text-sm text-gray-500 bg-gray-50 rounded-lg p-4"
  >
    <p>Analysis completed in {results.processing_time?.toFixed(1) || 'N/A'} seconds</p>
    <p className="text-xs mt-1">Request ID: {results.request_id?.slice(0, 8)}...</p>
  </motion.div>
);

export default App;
