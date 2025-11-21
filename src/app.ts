import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import uploadRouter from './routes/upload.route';

const app = express();

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

app.use('/upload', uploadRouter);

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

export default app;
