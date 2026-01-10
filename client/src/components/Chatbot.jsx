import React, { useState, useRef, useEffect } from 'react';
import { VscClose, VscSend, VscCommentDiscussion } from 'react-icons/vsc';

function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I\'m your DelhiFlow assistant. I can help you check flood risk for any ward in Delhi. Just type the ward name or number (e.g., "FATEH NAGAR", "Ward 5", or "5").',
      timestamp: new Date()
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  
  const API_BASE = import.meta.env.VITE_API_BASE || window.__API_BASE__ || 'http://127.0.0.1:8000';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    
    // Add user message to chat
    const newUserMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, newUserMessage]);
    setIsLoading(true);

    try {
      const base = API_BASE?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
      const response = await fetch(`${base}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Add assistant response to chat
      const assistantMessage = {
        role: 'assistant',
        content: data.response || 'Sorry, I couldn\'t process your request. Please try again.',
        timestamp: new Date(),
        wardData: data.ward_data
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please make sure the server is running and try again.',
        timestamp: new Date(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (date) => {
    return new Date(date).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <>
      {/* Chatbot Toggle Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 bg-gradient-to-br from-purple-500 to-fuchsia-500 hover:from-purple-600 hover:to-fuchsia-600 text-white rounded-full p-4 shadow-2xl shadow-purple-500/50 hover:scale-110 transition-all duration-300 flex items-center justify-center group"
          aria-label="Open chatbot"
        >
          <VscCommentDiscussion className="w-6 h-6 group-hover:scale-110 transition-transform" />
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full border-2 border-white animate-pulse"></span>
        </button>
      )}

      {/* Chatbot Window */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-96 max-w-[calc(100vw-3rem)] h-[600px] max-h-[calc(100vh-8rem)] bg-black/95 backdrop-blur-xl border border-purple-400/30 rounded-3xl shadow-2xl shadow-purple-900/50 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-purple-900/50 to-fuchsia-900/50 border-b border-purple-400/30 p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-br from-purple-500 to-fuchsia-500 rounded-xl p-2">
                <VscCommentDiscussion className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-white font-semibold text-sm">DelhiFlow Assistant</h3>
                <p className="text-purple-300/70 text-xs">Ask about flood risks</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-purple-300/70 hover:text-white hover:bg-purple-500/20 rounded-lg p-1.5 transition-all"
              aria-label="Close chatbot"
            >
              <VscClose className="w-5 h-5" />
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-purple-500/30 scrollbar-track-transparent">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-br from-purple-500 to-fuchsia-500 text-white'
                      : msg.isError
                      ? 'bg-red-500/20 border border-red-400/30 text-red-300'
                      : 'bg-purple-900/30 border border-purple-400/30 text-white'
                  }`}
                >
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  {msg.wardData && (
                    <div className="mt-2 pt-2 border-t border-purple-400/20">
                      <p className="text-xs opacity-80 font-medium mb-1">Ward: {msg.wardData.ward_name}</p>
                      <p className="text-xs opacity-70">
                        Risk: {msg.wardData.flood_prediction?.Flood_Risk_Class || 'N/A'}
                      </p>
                    </div>
                  )}
                  <p className="text-xs opacity-60 mt-1.5">{formatTime(msg.timestamp)}</p>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-purple-900/30 border border-purple-400/30 rounded-2xl px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-purple-400/30 p-4 bg-purple-900/20">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type ward name (e.g., FATEH NAGAR, Ward 5)..."
                disabled={isLoading}
                className="flex-1 bg-purple-900/30 border border-purple-400/30 rounded-xl px-4 py-2.5 text-white placeholder-purple-400/50 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <button
                onClick={handleSend}
                disabled={!inputMessage.trim() || isLoading}
                className="bg-gradient-to-br from-purple-500 to-fuchsia-500 hover:from-purple-600 hover:to-fuchsia-600 disabled:from-purple-500/50 disabled:to-fuchsia-500/50 text-white rounded-xl p-2.5 transition-all duration-200 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
                aria-label="Send message"
              >
                <VscSend className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-purple-400/50 mt-2 px-1">
              Press Enter to send, Shift+Enter for new line
            </p>
          </div>
        </div>
      )}
    </>
  );
}

export default Chatbot;

