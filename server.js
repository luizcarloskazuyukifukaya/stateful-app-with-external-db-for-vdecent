const express = require('express');
const { Pool } = require('pg');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 80;

// Database Configuration
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  // For local development with a local postgres, we might not want SSL.
  // In many cloud environments, SSL is preferred but for simplicity with Coolify's internal network, we can often skip it.
  ssl: process.env.DATABASE_URL?.includes('localhost') || process.env.DATABASE_URL?.includes('db') ? false : { rejectUnauthorized: false }
});

// Middleware
app.use(express.json());
app.use(express.static('public'));

// Basic Logging Middleware
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

// Database Initialization with Retry
const initDb = async (retries = 5, delay = 5000) => {
  for (let i = 0; i < retries; i++) {
    try {
      await pool.query(`
        CREATE TABLE IF NOT EXISTS activities (
          id SERIAL PRIMARY KEY,
          activity_type VARCHAR(50) NOT NULL,
          start_time TIMESTAMP NOT NULL,
          end_time TIMESTAMP NOT NULL,
          details TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);
      console.log('Database initialized successfully');
      return;
    } catch (err) {
      console.error(`Database initialization attempt ${i + 1} failed:`, err.message);
      if (i < retries - 1) {
        console.log(`Retrying in ${delay / 1000}s...`);
        await new Promise(res => setTimeout(res, delay));
      } else {
        console.error('Max retries reached. Database initialization failed.');
      }
    }
  }
};

// Health Check Endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'UP', timestamp: new Date().toISOString() });
});

// API Endpoint: Get all activities
app.get('/api/activities', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM activities ORDER BY start_time DESC');
    res.json(result.rows);
  } catch (err) {
    console.error('Error fetching activities:', err);
    res.status(500).json({ error: 'Database error' });
  }
});

// API Endpoint: Save a new activity
app.post('/api/activities', async (req, res) => {
  const { activity_type, start_time, end_time, details } = req.body;
  
  if (!activity_type || !start_time || !end_time) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const query = 'INSERT INTO activities (activity_type, start_time, end_time, details) VALUES ($1, $2, $3, $4) RETURNING *';
    const values = [activity_type, start_time, end_time, details];
    const result = await pool.query(query, values);
    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error('Error saving activity:', err);
    res.status(500).json({ error: 'Database error' });
  }
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
  initDb();
});
