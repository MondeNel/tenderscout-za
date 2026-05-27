import React, { useState, useContext, useEffect } from 'react';
import { AuthContext } from '../context/AuthContext';
import IndustryCheckboxGroup from '../components/IndustryCheckboxGroup';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Profile = () => {
  const { currentUser, updateUser } = useContext(AuthContext);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    company_name: '',
    registration_number: '',
    bee_level: '',
    company_size: '',
    industries: [],
    business_location: '',
    business_lat: '',
    business_lng: '',
    search_radius_km: 100,
    province_preferences: [],
    town_preferences: [],
    municipality_preferences: [],
  });
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (currentUser) {
      setForm({
        company_name: currentUser.company_name || '',
        registration_number: currentUser.registration_number || '',
        bee_level: currentUser.bee_level || '',
        company_size: currentUser.company_size || '',
        industries: currentUser.industry_preferences || [],
        business_location: currentUser.business_location || '',
        business_lat: currentUser.business_lat?.toString() || '',
        business_lng: currentUser.business_lng?.toString() || '',
        search_radius_km: currentUser.search_radius_km || 100,
        province_preferences: currentUser.province_preferences || [],
        town_preferences: currentUser.town_preferences || [],
        municipality_preferences: currentUser.municipality_preferences || [],
      });
    }
  }, [currentUser]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        company_name: form.company_name,
        registration_number: form.registration_number,
        bee_level: form.bee_level,
        company_size: form.company_size,
        industry_preferences: form.industries,
        business_location: form.business_location,
        business_lat: form.business_lat ? parseFloat(form.business_lat) : null,
        business_lng: form.business_lng ? parseFloat(form.business_lng) : null,
        search_radius_km: parseInt(form.search_radius_km),
        province_preferences: form.province_preferences,
        town_preferences: form.town_preferences,
        municipality_preferences: form.municipality_preferences,
      };
      const { data } = await axios.put(`${API_BASE}/user/preferences`, payload, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      });
      updateUser(data); // update context with new user data
      setMessage('Profile updated successfully');
      setEditing(false);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Update failed');
    }
  };

  if (!currentUser) return <div>Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Company Profile</h1>
      {message && <p className="mb-4 text-green-600">{message}</p>}
      {!editing ? (
        <div className="space-y-2">
          <p><strong>Company:</strong> {currentUser.company_name || 'N/A'}</p>
          <p><strong>Reg No:</strong> {currentUser.registration_number || 'N/A'}</p>
          <p><strong>BEE Level:</strong> {currentUser.bee_level || 'N/A'}</p>
          <p><strong>Size:</strong> {currentUser.company_size || 'N/A'}</p>
          <p><strong>Industries:</strong> {currentUser.industry_preferences?.join(', ') || 'None selected'}</p>
          <p><strong>Location:</strong> {currentUser.business_location || 'N/A'}</p>
          <button onClick={() => setEditing(true)} className="mt-4 bg-indigo-600 text-white px-4 py-2 rounded">Edit Profile</button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm">Company Name</label>
              <input name="company_name" value={form.company_name} onChange={handleChange} className="mt-1 block w-full rounded border-gray-300" />
            </div>
            <div>
              <label className="block text-sm">Reg Number</label>
              <input name="registration_number" value={form.registration_number} onChange={handleChange} className="mt-1 block w-full rounded border-gray-300" />
            </div>
            <div>
              <label className="block text-sm">BEE Level</label>
              <select name="bee_level" value={form.bee_level} onChange={handleChange} className="mt-1 block w-full rounded border-gray-300">
                <option value="">Select</option>
                <option value="1">Level 1</option>
                <option value="2">Level 2</option>
                <option value="3">Level 3</option>
                <option value="4">Level 4</option>
                <option value="Non-compliant">Non-compliant</option>
              </select>
            </div>
            <div>
              <label className="block text-sm">Company Size</label>
              <select name="company_size" value={form.company_size} onChange={handleChange} className="mt-1 block w-full rounded border-gray-300">
                <option value="">Select</option>
                <option value="Micro">Micro</option>
                <option value="Small">Small</option>
                <option value="Medium">Medium</option>
                <option value="Large">Large</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm mb-1">Industries</label>
            <IndustryCheckboxGroup selected={form.industries} onChange={(inds) => setForm({...form, industries: inds})} />
          </div>
          <button type="submit" className="bg-green-600 text-white px-4 py-2 rounded">Save</button>
          <button type="button" onClick={() => setEditing(false)} className="ml-2 bg-gray-300 px-4 py-2 rounded">Cancel</button>
        </form>
      )}
    </div>
  );
};

export default Profile;