# Use an official PHP runtime with Apache
FROM php:7.2-apache

# Copy all phishing kits into the container
COPY ./src /var/www/html

# Update the default apache site with custom config
ADD apache.conf /etc/apache2/sites-enabled/000-default.conf

# Expose the port Apache listens on
EXPOSE 80

# Start Apache when the container runs
CMD ["apache2-foreground"]