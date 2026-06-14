import React, { useState, useEffect, useRef } from 'react';
import { 
  Camera, AlertTriangle, Play, Square, ShieldAlert, 
  TrendingUp, Activity, ShieldCheck, Upload, Maximize2, X 
} from 'lucide-react';
import { 
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, 
  Tooltip, Cell, PieChart, Pie
} from 'recharts';

const BACKEND_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

function App() {
  const [frame, setFrame] = useState(null);
  const [stats, setStats] = useState({ cars: 0, bikes: 0, buses: 0, trucks: 0, total: 0 });
  const [violations, setViolations] = useState([]);
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState('');
  const [status, setStatus] = useState('disconnected'); // disconnected, connected, processing
  const [uploading, setUploading] = useState(false);
  const [modalData, setModalData] = useState(null); // { image, type, time, details }

  const wsRef = useRef(null);
  const fileInputRef = useRef(null);

  // Load initial videos and violation logs
  useEffect(() => {
    fetchVideos();
    fetchViolations();
    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const connectWebSocket = () => {
    console.log("Connecting to WebSocket...");
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      setStatus(prev => prev === 'processing' ? 'processing' : 'connected');
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setStatus('disconnected');
      // Retry connection after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'frame') {
          setFrame(data.frame);
          setStats(data.stats);
          
          // If there are new violations, append them to state
          if (data.violations && data.violations.length > 0) {
            setViolations(prev => [...data.violations, ...prev]);
            
            // Check if any of the new violations is an accident to alert
            const containsAccident = data.violations.some(v => v.type === 'Accident');
            if (containsAccident) {
              triggerAudioAlert();
            }
          }
          setStatus('processing');
        } else if (data.type === 'status' && data.status === 'stopped') {
          setStatus('connected');
          setFrame(null);
        }
      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };
  };

  const fetchVideos = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/videos`);
      const data = await res.json();
      setVideos(data.videos || []);
      if (data.videos && data.videos.length > 0) {
        setSelectedVideo(data.videos[0]);
      }
    } catch (err) {
      console.error("Error fetching videos:", err);
    }
  };

  const fetchViolations = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/violations`);
      const data = await res.json();
      // Format backend response
      const formatted = data.map(v => ({
        id: v.id,
        type: v.violation_type,
        vehicle_id: v.vehicle_id,
        vehicle_type: v.vehicle_type,
        speed: v.speed,
        screenshot: `${BACKEND_URL}${v.screenshot_path}`,
        timestamp: new Date(v.timestamp).toLocaleString()
      }));
      setViolations(formatted);
    } catch (err) {
      console.error("Error fetching violations:", err);
    }
  };

  const startStream = async () => {
    if (!selectedVideo) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/start?video_name=${selectedVideo}`, {
        method: 'POST'
      });
      if (res.ok) {
        setStatus('processing');
      } else {
        const data = await res.json();
        alert(`Error: ${data.detail}`);
      }
    } catch (err) {
      console.error("Error starting stream:", err);
    }
  };

  const stopStream = async () => {
    try {
      await fetch(`${BACKEND_URL}/api/stop`, { method: 'POST' });
      setStatus('connected');
      setFrame(null);
    } catch (err) {
      console.error("Error stopping stream:", err);
    }
  };

  const handleUploadClick = () => {
    if (fileInputRef.current) fileInputRef.current.click();
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/upload`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        await fetchVideos();
        setSelectedVideo(data.filename);
        alert("Video uploaded successfully!");
      } else {
        alert("Upload failed.");
      }
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
    }
  };

  const triggerAudioAlert = () => {
    // Generate a clean synthesizer sound indicating emergency alert
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      oscillator.type = 'sawtooth';
      oscillator.frequency.setValueAtTime(440, audioCtx.currentTime); // A4
      oscillator.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.15); // A5
      oscillator.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.3);
      
      gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.6);
      
      oscillator.start(audioCtx.currentTime);
      oscillator.stop(audioCtx.currentTime + 0.6);
    } catch (e) {
      console.log("Audio API failed to initialize", e);
    }
  };

  // Prepare chart data
  const pieData = [
    { name: 'Cars', value: stats.cars, color: '#3b82f6' },
    { name: 'Bikes', value: stats.bikes, color: '#10b981' },
    { name: 'Buses', value: stats.buses, color: '#f59e0b' },
    { name: 'Trucks', value: stats.trucks, color: '#ef4444' }
  ].filter(d => d.value > 0);

  // Default mock data if no vehicles processed yet to render nice placeholder graphs
  const chartData = pieData.length > 0 ? pieData : [
    { name: 'Cars', value: 12, color: '#3b82f6' },
    { name: 'Bikes', value: 8, color: '#10b981' },
    { name: 'Buses', value: 3, color: '#f59e0b' },
    { name: 'Trucks', value: 2, color: '#ef4444' }
  ];

  // Count violations by category
  const overspeedCount = violations.filter(v => v.type === 'Overspeeding').length;
  const noHelmetCount = violations.filter(v => v.type === 'No Helmet').length;
  const accidentCount = violations.filter(v => v.type === 'Accident').length;

  const violationStats = [
    { name: 'Overspeeding', count: overspeedCount, fill: '#f59e0b' },
    { name: 'No Helmet', count: noHelmetCount, fill: '#ef4444' },
    { name: 'Accidents', count: accidentCount, fill: '#8b5cf6' }
  ];

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="header">
        <div className="brand-section">
          <div className="brand-logo">AI</div>
          <div className="brand-title">
            <h1>Smart Traffic Analytics</h1>
            <p>Real-Time Monitoring & Violation Detection</p>
          </div>
        </div>

        <div className="controls-section">
          {/* Status Badge */}
          <div className="status-badge">
            <span className={`status-dot ${status === 'connected' ? 'online' : status === 'processing' ? 'processing' : ''}`} />
            <span>
              {status === 'disconnected' ? 'DISCONNECTED' : status === 'connected' ? 'CONNECTED' : 'PROCESSING FEED'}
            </span>
          </div>

          {/* Video List Selector */}
          <select 
            className="video-selector" 
            value={selectedVideo} 
            onChange={(e) => setSelectedVideo(e.target.value)}
            disabled={status === 'processing'}
          >
            {videos.length === 0 ? (
              <option value="">No videos available</option>
            ) : (
              videos.map((vid, idx) => (
                <option key={idx} value={vid}>{vid}</option>
              ))
            )}
          </select>

          {/* Upload Button */}
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            accept="video/*" 
            style={{ display: 'none' }} 
          />
          <button 
            className="btn btn-secondary" 
            style={{ border: '1px solid var(--panel-border)', background: 'rgba(255, 255, 255, 0.05)', color: 'white' }}
            onClick={handleUploadClick}
            disabled={uploading || status === 'processing'}
          >
            <Upload size={16} />
            {uploading ? "Uploading..." : "Upload Video"}
          </button>

          {/* Start/Stop Processing Controls */}
          {status !== 'processing' ? (
            <button className="btn btn-primary" onClick={startStream} disabled={!selectedVideo}>
              <Play size={16} fill="white" />
              Analyze Video
            </button>
          ) : (
            <button className="btn btn-danger" onClick={stopStream}>
              <Square size={16} fill="white" />
              Stop Analysis
            </button>
          )}
        </div>
      </header>

      {/* Stats Cards Row */}
      <section className="stats-grid">
        <div className="stat-card cars">
          <div className="stat-info">
            <h3>Unique Cars</h3>
            <p className="stat-value">{stats.cars}</p>
          </div>
          <div className="stat-icon">
            <Activity size={24} />
          </div>
        </div>
        
        <div className="stat-card bikes">
          <div className="stat-info">
            <h3>Unique Motorcycles</h3>
            <p className="stat-value">{stats.bikes}</p>
          </div>
          <div className="stat-icon">
            <ShieldCheck size={24} />
          </div>
        </div>

        <div className="stat-card heavy">
          <div className="stat-info">
            <h3>Buses & Trucks</h3>
            <p className="stat-value">{stats.buses + stats.trucks}</p>
          </div>
          <div className="stat-icon">
            <TrendingUp size={24} />
          </div>
        </div>

        <div className="stat-card total">
          <div className="stat-info">
            <h3>Total Unique Vehicles</h3>
            <p className="stat-value">{stats.total}</p>
          </div>
          <div className="stat-icon">
            <Camera size={24} />
          </div>
        </div>
      </section>

      {/* Main content grid */}
      <main className="main-layout">
        
        {/* Left Side: Video Frame stream */}
        <section className="feed-container">
          <div className="section-title">
            <h2><Camera size={20} /> Live Traffic Camera Analysis</h2>
            {status === 'processing' && <span className="status-badge" style={{ color: 'var(--accent-orange)' }}>GPU ACTIVE</span>}
          </div>

          <div className="video-player-wrapper">
            {frame ? (
              <img className="video-frame" src={frame} alt="Annotated Traffic Feed" />
            ) : (
              <div className="placeholder-video">
                <div className="placeholder-icon">
                  <Play size={32} />
                </div>
                <div>
                  <h3>No Active Stream</h3>
                  <p>Select a video from the header dropdown and click "Analyze Video" to start real-time computer vision processing.</p>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Right Side: Violations Log */}
        <section className="violations-container">
          <div className="section-title">
            <h2><ShieldAlert size={20} /> Real-Time Traffic Violations</h2>
            {violations.length > 0 && (
              <span className="status-badge" style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--accent-red)', border: '1px solid rgba(239,68,68,0.2)' }}>
                {violations.length} LOGS
              </span>
            )}
          </div>

          <div className="violations-list">
            {violations.length === 0 ? (
              <div className="no-violations">
                <ShieldCheck size={48} style={{ color: 'var(--accent-green)', marginBottom: '12px' }} />
                <h3>No Violations Logged</h3>
                <p>System is monitoring traffic rules. Infractions will be captured and displayed here.</p>
              </div>
            ) : (
              violations.map((violation) => (
                <div key={violation.id} className={`violation-card ${violation.type.toLowerCase().replace(' ', '-')}`}>
                  
                  {/* Screenshot Thumbnail */}
                  <div className="violation-thumb" onClick={() => setModalData(violation)}>
                    <img src={violation.screenshot} alt="Screenshot" />
                  </div>

                  {/* Violation details */}
                  <div className="violation-details">
                    <div className="violation-badge-row">
                      <span className="violation-badge">{violation.type}</span>
                      <span className="violation-time">{violation.timestamp}</span>
                    </div>

                    <div className="violation-text">
                      {violation.type === 'Overspeeding' ? (
                        <>Vehicle #{violation.vehicle_id} exceeded speed limit at <span>{violation.speed} km/h</span></>
                      ) : violation.type === 'No Helmet' ? (
                        <>Motorcyclist #{violation.vehicle_id} detected riding <span>without a helmet</span></>
                      ) : (
                        <span style={{ color: 'var(--accent-red)' }}>CRITICAL: Vehicle collision/accident detected!</span>
                      )}
                    </div>

                    <div className="violation-meta">
                      {violation.vehicle_type && (
                        <>Vehicle Type: <span>{violation.vehicle_type.toUpperCase()}</span></>
                      )}
                      {violation.vehicle_id && (
                        <> | ID: <span>#{violation.vehicle_id}</span></>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {/* Analytics Charts */}
      <section className="analytics-section">
        <div className="chart-card">
          <h2>Traffic Distribution Analysis</h2>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: '8px', color: 'white' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <h2>Violation Analytics</h2>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={violationStats}>
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: '8px', color: 'white' }} />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {violationStats.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* Full Image Modal Viewer */}
      {modalData && (
        <div className="modal-overlay" onClick={() => setModalData(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setModalData(null)}>
              <X size={20} />
            </button>
            <img src={modalData.screenshot} alt="Full Size Violation Screenshot" />
            <div className="modal-caption">
              <h3>{modalData.type} - Alert Details</h3>
              <p>Timestamp: {modalData.timestamp} | {modalData.type === 'Overspeeding' ? `Recorded Speed: ${modalData.speed} km/h` : 'No helmet violation caught on camera.'}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
