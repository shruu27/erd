// api/client.js — all backend calls in one place

async function post(path, body) {
  var res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    var err = await res.json().catch(function () {
      return { detail: res.statusText };
    });
    throw new Error(err.detail || res.statusText);
  }

  return res.json();
}

export function generateModel(userQuery, operation, existingModel) {
  return post('/workflow/generate', {
    user_query: userQuery,
    operation: operation || '',
    existing_model: existingModel || null,
  });
}

export function validateAndGenerateSQL(dataModel, operation) {
  return post('/workflow/validate', {
    data_model: dataModel,
    operation: operation,
  });
}

export function approveAndGenerateSQL(dataModel, operation) {
  return post('/workflow/approve', {
    data_model: dataModel,
    operation: operation,
  });
}

export function applyFeedbackAndGenerateSQL(dataModel, feedback, operation) {
  return post('/workflow/feedback', {
    data_model: dataModel,
    feedback: feedback,
    operation: operation,
  });
}

export function generateERD(sqlOutput, format = 'svg') {
  return post('/workflow/generate-erd', {
    sql_output: sqlOutput,
    format: format,
  });
}