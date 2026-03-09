import { useState } from 'react';

import { Header } from './components/ui/Header';
import { InputForm } from './components/InputForm';
import { ModelReview } from './components/ModelReview';
import { SQLView } from './components/SQLView';
import { ERDView } from './components/ERDView';

import {
  generateModel,
  validateAndGenerateSQL,
  approveAndGenerateSQL,
  applyFeedbackAndGenerateSQL,
  generateERD,
} from './api/client';

const BG = '#0d0f14';

export default function App() {
  const [step, setStep] = useState(0);
  const [operation, setOperation] = useState('CREATE');
  const [validationMode, setValidationMode] = useState('auto');
  const [dataModel, setDataModel] = useState(null);
  const [validation, setValidation] = useState(null);
  const [sqlOutput, setSqlOutput] = useState(null);
  const [diagram, setDiagram] = useState(null);
  const [erdFormat, setErdFormat] = useState('svg');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function wrap(fn) {
    setLoading(true);
    setError('');
    fn()
      .catch((e) => setError(e?.message || 'Unexpected error'))
      .finally(() => setLoading(false));
  }

  function reset() {
    setStep(0);
    setDataModel(null);
    setValidation(null);
    setSqlOutput(null);
    setDiagram(null);
    setError('');
    setOperation('CREATE');
    setValidationMode('auto');
  }

  function handleGenerate(opts) {
    wrap(async function () {
      const res = await generateModel(opts.userQuery, opts.operation, opts.existingModel);
      setDataModel(res.data_model);
      setOperation(res.operation || opts.operation || 'CREATE');
      setValidationMode(opts.validationMode || 'auto');
      setValidation(null);
      setStep(1);
    });
  }

  function handleAutoValidate() {
    wrap(async function () {
      const res = await validateAndGenerateSQL(dataModel, operation);
      setValidation(res.validation);
      if (res.sql_output && Object.keys(res.sql_output).length > 0) {
        setSqlOutput(res.sql_output);
        setStep(2);
      }
    });
  }

  function handleApprove() {
    wrap(async function () {
      const res = await approveAndGenerateSQL(dataModel, operation);
      setSqlOutput(res.sql_output);
      setStep(2);
    });
  }

  function handleFeedback(feedbackText) {
    wrap(async function () {
      const res = await applyFeedbackAndGenerateSQL(dataModel, feedbackText, operation);
      setDataModel(res.data_model);
      if (res.sql_output && Object.keys(res.sql_output).length > 0) {
        setSqlOutput(res.sql_output);
        setDiagram(null);
        setStep(2);
      }
    });
  }

  function handleGenerateERD() {
    wrap(async function () {
      const res = await generateERD(sqlOutput, erdFormat);
      setDiagram(res);
      setStep(3);
    });
  }

  function handleDownloadERD() {
    if (!diagram || !diagram.diagram_data) return;
    
    const mimeType = 
      diagram.format === 'png' ? 'image/png' :
      diagram.format === 'pdf' ? 'application/pdf' :
      'image/svg+xml';
    
    const extension = diagram.format || 'svg';
    const link = document.createElement('a');
    link.href = `data:${mimeType};base64,${diagram.diagram_data}`;
    link.download = `erd_diagram.${extension}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  return (
    <div
      style={{
        background: BG,
        minHeight: '100vh',
        color: '#e2e8f0',
        fontFamily: '"DM Sans", system-ui, sans-serif',
      }}
    >
      <style>
        {`@keyframes spin { to { transform: rotate(360deg); } }`}
      </style>

      <Header step={step} onReset={reset} />

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 40px' }}>
        {step === 0 && (
          <InputForm onSubmit={handleGenerate} loading={loading} error={error} />
        )}

        {step === 1 && (
          <ModelReview
            dataModel={dataModel}
            operation={operation}
            validationMode={validationMode}
            validation={validation}
            loading={loading}
            error={error}
            onAutoValidate={handleAutoValidate}
            onApprove={handleApprove}
            onFeedback={handleFeedback}
          />
        )}

        {step === 2 && (
          <SQLView
            sqlOutput={sqlOutput}
            validation={validation}
            onBack={() => setStep(1)}
            onReset={reset}
            onGenerateERD={handleGenerateERD}
          />
        )}

        {step === 3 && (
          <ERDView
            loading={loading}
            error={error}
            diagram={diagram}
            format={erdFormat}
            onBack={() => setStep(2)}
            onReset={reset}
            onDownload={handleDownloadERD}
          />
        )}
      </div>
    </div>
  );
}