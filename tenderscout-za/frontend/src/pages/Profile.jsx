/**
 * File: src/pages/Profile.jsx
 * Purpose: Company Profile Page — view and edit company details,
 *          including industry preferences.
 *
 * This component lets the user see their saved company profile
 * (name, registration number, BEE level, size, industries, location)
 * and switch to an editing mode where they can update any field.
 *
 * It uses the AuthContext to read the current user and to update
 * the context after a successful save, so the rest of the app
 * immediately reflects the new profile data.
 */

import React, { useState, useContext, useEffect } from 'react';
import { AuthContext } from '../context/AuthContext';
import IndustryCheckboxGroup from '../components/IndustryCheckboxGroup';
import axios from 'axios';

// Base URL for the backend API — defaults to localhost in development
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Profile = () => {
  // ---------------------------------------------------------------------------
  // Context – currentUser is the logged‑in user; updateUser updates the context
  // after a successful profile edit.
  // ---------------------------------------------------------------------------
  const { currentUser, updateUser } = useContext(AuthContext);

  // Toggle between viewing (false) and editing (true)
  const [editing, setEditing] = useState(false);

  // Local form state — initialised from currentUser whenever the user changes
  const [form, setForm] = useState({
    company_name: '',
    registration_number: '',
    bee_level: '',
    company_size: '',
    industries: [],          // selected industry names
    business_location: '',
    business_lat: '',        // stored as string to keep the input field happy
    business_lng: '',
    search_radius_km: 100,
    province_preferences: [],
    town_preferences: [],
    municipality_preferences: [],
  });

  // Success or error message shown at the top of the card
  const [message, setMessage] = useState('');

  // ---------------------------------------------------------------------------
  // Populate the form whenever the user object changes (e.g., after login or
  // context refresh). Coordinates are converted to strings for the text inputs.
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Generic input handler – updates the corresponding field in local state.
  // ---------------------------------------------------------------------------
  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  // ---------------------------------------------------------------------------
  // Save handler – builds the payload (converting coordinate strings back to
  // floats), calls PUT /user/preferences, updates the AuthContext, and returns
  // to view mode on success.
  // ---------------------------------------------------------------------------
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
      updateUser(data); // immediately reflect changes across the app
      setMessage('Profile updated successfully');
      setEditing(false);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Update failed');
    }
  };

  // ---------------------------------------------------------------------------
  // Guard – if the user hasn't loaded yet, show a loading message.
  // In practice the AuthContext provides this quickly.
  // ---------------------------------------------------------------------------
  if (!currentUser) return <div>Loading...</div>;

  // ---------------------------------------------------------------------------
  // RENDER
  // ---------------------------------------------------------------------------
  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Company Profile</h1>

      {/* Status message (success or error) */}
      {message && <p className="mb-4 text-green-600">{message}</p>}

      {!editing ? (
        /* ===================================================================
           VIEW MODE – shows all company fields as plain text.
           The user clicks "Edit Profile" to switch to editing mode.
           =================================================================== */
        <div className="space-y-2">
          <p><strong>Company:</strong> {currentUser.company_name || 'N/A'}</p>
          <p><strong>Reg No:</strong> {currentUser.registration_number || 'N/A'}</p>
          <p><strong>BEE Level:</strong> {currentUser.bee_level || 'N/A'}</p>
          <p><strong>Size:</strong> {currentUser.company_size || 'N/A'}</p>
          <p><strong>Industries:</strong> {currentUser.industry_preferences?.join(', ') || 'None selected'}</p>
          <p><strong>Location:</strong> {currentUser.business_location || 'N/A'}</p>
          <button onClick={() => setEditing(true)} className="mt-4 bg-indigo-600 text-white px-4 py-2 rounded">
            Edit Profile
          </button>
        </div>
      ) : (
        /* ===================================================================
           EDIT MODE – form with all fields.
           Industries use the reusable IndustryCheckboxGroup component.
           The Cancel button discards changes and returns to view mode.
           =================================================================== */
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