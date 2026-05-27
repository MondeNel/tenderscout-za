import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const fetchIndustries = async () => {
  const token = localStorage.getItem('access_token');
  const { data } = await axios.get(`${API_BASE}/user/industries`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return data;
};