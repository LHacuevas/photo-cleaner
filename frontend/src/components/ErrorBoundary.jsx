import { Component } from 'react';
import './ErrorBoundary.css';

// Shows a recovery screen instead of a blank page when a render error escapes a page
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div className="error-boundary">
        <h2>Something went wrong</h2>
        <p>{this.state.error.message}</p>
        <div className="error-boundary-actions">
          <button className="btn btn-primary" onClick={() => window.location.reload()}>
            Reload
          </button>
          <button className="btn btn-secondary" onClick={() => window.location.assign('/')}>
            Back to Home
          </button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
